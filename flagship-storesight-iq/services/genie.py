"""
Genie API Client for AI-powered natural language queries.

Uses Databricks AI/BI Genie to answer questions about store data.
https://docs.databricks.com/en/ai/genie/index.html

Example queries:
- "Which store had the highest sales last week?"
- "Compare Store #5 vs Store #12 performance"
- "Why did Store #22's labor costs increase?"
"""

import logging
from typing import Dict, List, Any, Optional
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieMessage

logger = logging.getLogger(__name__)


class GenieClient:
    """Client for Databricks Genie API."""

    def __init__(self, genie_space_id: Optional[str] = None):
        """
        Initialize Genie client.

        Args:
            genie_space_id: Genie Space ID (can also be set via GENIE_SPACE_ID env var)
        """
        self._client: Optional[WorkspaceClient] = None
        self._genie_space_id = genie_space_id

    @property
    def client(self) -> WorkspaceClient:
        """Lazy initialization of WorkspaceClient."""
        if self._client is None:
            self._client = WorkspaceClient()
        return self._client

    @property
    def genie_space_id(self) -> str:
        """Get Genie Space ID from init or environment."""
        if self._genie_space_id:
            return self._genie_space_id

        import os
        space_id = os.getenv("GENIE_SPACE_ID")
        if not space_id:
            raise ValueError(
                "Genie Space ID not configured. "
                "Set GENIE_SPACE_ID environment variable or run setup notebook."
            )
        return space_id

    def start_conversation(self, question: str) -> Dict[str, Any]:
        """
        Start a new conversation with Genie.

        Args:
            question: Natural language question about store data

        Returns:
            {
                "conversation_id": str,
                "message_id": str,
                "response": str,
                "data": Optional[List[Dict]],  # Query results if applicable
                "sql": Optional[str],  # Generated SQL if applicable
            }
        """
        try:
            conversation = self.client.genie.start_conversation_and_wait(
                self.genie_space_id,
                question
            )
            return self._process_response(conversation)
        except Exception as e:
            logger.error(f"Genie conversation failed: {e}")
            raise

    def continue_conversation(
        self,
        conversation_id: str,
        question: str
    ) -> Dict[str, Any]:
        """
        Continue an existing conversation with a follow-up question.

        Args:
            conversation_id: ID from previous conversation
            question: Follow-up question

        Returns:
            Same format as start_conversation
        """
        try:
            conversation = self.client.genie.create_message_and_wait(
                self.genie_space_id,
                conversation_id,
                question
            )
            return self._process_response(conversation)
        except Exception as e:
            logger.error(f"Genie follow-up failed: {e}")
            raise

    def _process_response(self, response: GenieMessage) -> Dict[str, Any]:
        """Process Genie response into structured format."""
        result = {
            "conversation_id": response.conversation_id,
            "message_id": response.message_id,
            "response": "",
            "data": None,
            "sql": None,
        }

        # Collect response text parts (NOT user's message)
        text_parts = []
        query_description = None
        analysis_text = None

        # Log top-level fields (content is the USER's message, not Genie's response)
        logger.debug(f"Genie response - user message (content): {response.content[:50] if response.content else 'None'}...")
        logger.info(f"Genie response attachments count: {len(response.attachments)}")
        
        # Try to get full response dict to see all fields
        try:
            response_dict = response.as_dict() if hasattr(response, 'as_dict') else {}
            # Look for any field containing "analysis", "summary", "result" in the full dict
            import json
            logger.debug(f"Full response dict keys: {list(response_dict.keys())}")
            for key, value in response_dict.items():
                if isinstance(value, str) and len(value) > 50:
                    logger.debug(f"Response dict {key}: {value[:150]}...")
        except Exception as e:
            logger.debug(f"Could not get response dict: {e}")

        for i, attachment in enumerate(response.attachments):
            # Log attachment structure
            attachment_fields = [attr for attr in dir(attachment) if not attr.startswith('_')]
            logger.debug(f"Attachment {i} fields: {attachment_fields}")
            
            # Check for query attachment - may contain analysis
            if attachment.query:
                query = attachment.query
                result["sql"] = query.query
                
                # Log all query fields to find the analysis text
                query_fields = [attr for attr in dir(query) if not attr.startswith('_')]
                logger.info(f"Query attachment fields: {query_fields}")
                
                # Look for analysis/result text in various possible fields
                for field in ['analysis', 'result', 'result_description', 'summary', 'answer', 'response_text']:
                    if hasattr(query, field):
                        val = getattr(query, field)
                        if val and isinstance(val, str):
                            logger.info(f"Found query.{field}: {val[:100]}...")
                            analysis_text = val
                            break
                
                # Fallback to description if no analysis found
                if not analysis_text:
                    query_description = query.description
                    logger.debug(f"Query description: {query_description[:100] if query_description else 'None'}...")

                # Get query results
                if response.query_result:
                    # Log query_result fields to find analysis
                    qr_fields = [attr for attr in dir(response.query_result) if not attr.startswith('_')]
                    logger.info(f"Query result fields: {qr_fields}")
                    
                    # Look for analysis/summary in query_result
                    for field in ['analysis', 'summary', 'description', 'result_summary', 'narrative', 'explanation']:
                        if hasattr(response.query_result, field):
                            val = getattr(response.query_result, field)
                            if val:
                                logger.info(f"Found query_result.{field}: {str(val)[:200]}...")
                                if isinstance(val, str) and not analysis_text:
                                    analysis_text = val
                    
                    if response.query_result.statement_id:
                        result["data"] = self._get_query_result(
                            response.query_result.statement_id
                        )
            
            # Check for text attachment (follow-up questions, clarifications)
            if attachment.text and attachment.text.content:
                text_content = attachment.text.content
                logger.info(f"Text attachment: {text_content[:100]}...")
                text_parts.append(text_content)

        # Build response: prefer analysis > text attachments > query description
        response_parts = []
        
        if analysis_text:
            response_parts.append(analysis_text)
        
        if text_parts:
            response_parts.extend(text_parts)
        
        # Only use query description as absolute fallback if nothing else
        if not response_parts and query_description:
            response_parts.append(query_description)
        
        result["response"] = "\n\n".join(response_parts)
        logger.info(f"Genie response processed: {len(result['response'])} chars, has_data={result['data'] is not None}")

        return result

    def _get_query_result(self, statement_id: str) -> List[Dict]:
        """Fetch query results from statement execution."""
        try:
            result = self.client.statement_execution.get_statement(statement_id)
            
            if not result.result or not result.result.data_array:
                return []

            # Get column names
            columns = [col.name for col in result.manifest.schema.columns]

            # Convert to list of dicts
            data = []
            for row in result.result.data_array:
                data.append(dict(zip(columns, row)))

            # Handle pagination if needed
            next_chunk = result.result.next_chunk_index
            while next_chunk:
                chunk = self.client.statement_execution.get_statement_result_chunk_n(
                    statement_id, next_chunk
                )
                for row in chunk.data_array:
                    data.append(dict(zip(columns, row)))
                next_chunk = chunk.next_chunk_index

            return data

        except Exception as e:
            logger.error(f"Failed to get query results: {e}")
            return []

    def get_suggested_questions(self) -> List[str]:
        """
        Get suggested questions for the Genie Space.

        Returns common questions users might ask about store data.
        """
        return [
            "Which store had the highest sales last week?",
            "Compare Store #5 vs Store #12 performance",
            "Which stores are underperforming this month?",
            "What's the average labor cost percentage by store?",
            "Show me stores with inventory alerts",
            "Why did Store #22's labor costs increase?",
            "Rank stores by revenue per labor hour",
            "What are the top selling items this week?",
            "Which stores have the highest waste?",
            "Show sales trends for the past 30 days",
        ]

    def get_genie_url(self, conversation_id: str) -> str:
        """Get URL to open conversation in Genie UI."""
        host = self.client.config.host
        return f"{host}/genie/rooms/{self.genie_space_id}/chats/{conversation_id}"


# Singleton instance
genie_client = GenieClient()


