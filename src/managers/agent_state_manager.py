import logging
from typing import Optional, Dict
from src.db.enums import AgentState, ToolOperationState, ContentType
from src.tools.base import AgentDependencies, ToolRegistry, AgentResult
from enum import Enum

logger = logging.getLogger(__name__)

class AgentAction(Enum):
    """Actions that trigger agent state transitions"""
    START_TOOL = "start_tool"         # NORMAL_CHAT -> TOOL_OPERATION
    COMPLETE_TOOL = "complete_tool"   # TOOL_OPERATION -> NORMAL_CHAT
    CANCEL_TOOL = "cancel_tool"       # TOOL_OPERATION -> NORMAL_CHAT
    ERROR = "error"                   # Any -> NORMAL_CHAT

class AgentStateManager:
    def __init__(self, tool_state_manager, orchestrator, trigger_detector):
        self.current_state = AgentState.NORMAL_CHAT
        self.tool_state_manager = tool_state_manager
        self.orchestrator = orchestrator
        self.trigger_detector = trigger_detector
        self.active_operation = None
        self._current_tool_type = None  # Add tool type tracking
        
        # Define valid state transitions
        self.state_transitions = {
            (AgentState.NORMAL_CHAT, AgentAction.START_TOOL): AgentState.TOOL_OPERATION,
            (AgentState.TOOL_OPERATION, AgentAction.COMPLETE_TOOL): AgentState.NORMAL_CHAT,
            (AgentState.TOOL_OPERATION, AgentAction.CANCEL_TOOL): AgentState.NORMAL_CHAT,
            (AgentState.TOOL_OPERATION, AgentAction.ERROR): AgentState.NORMAL_CHAT,
            (AgentState.NORMAL_CHAT, AgentAction.ERROR): AgentState.NORMAL_CHAT,
        }

    async def _transition_state(self, action: AgentAction, reason: str = "") -> bool:
        """Handle state transitions with validation"""
        next_state = self.state_transitions.get((self.current_state, action))
        if next_state is None:
            logger.warning(f"Invalid state transition: {self.current_state} -> {action}")
            return False
            
        logger.info(f"State transition: {self.current_state} -> {next_state} ({reason})")
        self.current_state = next_state
        return True

    async def handle_agent_state(self, message: str, session_id: str) -> Dict:
        """Main state handling method"""
        try:
            if not message:
                return self._create_error_response("Invalid message received")

            # Store initial state
            initial_state = self.current_state
            logger.info(f"Current state before handling: {self.current_state}")

            # NORMAL_CHAT: Check for tool triggers
            if self.current_state == AgentState.NORMAL_CHAT:
                tool_type = self.trigger_detector.get_specific_tool_type(message)
                if tool_type:
                    try:
                        # Transition to TOOL_OPERATION state BEFORE handling operation
                        await self._transition_state(
                            AgentAction.START_TOOL,
                            f"Starting {tool_type} operation"
                        )
                        
                        # Store tool_type for the session
                        self._current_tool_type = tool_type
                        logger.info(f"Starting tool operation with type: {tool_type}")

                        # Now handle the tool operation
                        result = await self.orchestrator.handle_tool_operation(
                            message=message,
                            session_id=session_id,
                            tool_type=tool_type
                        )
                        
                        if isinstance(result, dict):
                            return {
                                **result,
                                "state": self.current_state.value,
                                "tool_type": tool_type
                            }
                    except Exception as e:
                        logger.error(f"Error starting tool operation: {e}")
                        # Don't transition state on error - let approval_manager handle it
                        return self._create_error_response(str(e))

            # TOOL_OPERATION: Handle ongoing operation
            elif self.current_state == AgentState.TOOL_OPERATION:
                try:
                    result = await self.orchestrator.handle_tool_operation(
                        message=message,
                        session_id=session_id,
                        tool_type=self._current_tool_type
                    )
                    
                    if isinstance(result, dict):
                        # Only transition state if explicitly completed/cancelled
                        operation_status = result.get("status", "").lower()
                        
                        # Check for both "completed" and "cancelled" status, as well as "exit" status
                        if operation_status in ["completed", "cancelled", "exit"]:
                            action = AgentAction.COMPLETE_TOOL if operation_status in ["completed", "exit"] else AgentAction.CANCEL_TOOL
                            await self._transition_state(action, f"Operation {operation_status}")
                            self._current_tool_type = None
                            logger.info(f"Transitioned to {self.current_state} after operation {operation_status}")
                        
                        return {
                            **result,
                            "state": self.current_state.value,
                            "response": result.get("response", "Processing your request...")
                        }
                except Exception as e:
                    logger.error(f"Error in tool operation: {e}")
                    # Let approval_manager handle the error state transition
                    return self._create_error_response(str(e))

            # Default response for NORMAL_CHAT
            return {
                "state": self.current_state.value,
                "status": "normal_chat"
            }

        except Exception as e:
            logger.error(f"Error in state management: {e}")
            # Don't transition state here - let approval_manager handle it
            return self._create_error_response(str(e))

    def _create_error_response(self, error_message: str) -> Dict:
        """Create standardized error response"""
        return {
            "state": self.current_state.value,
            "error": error_message,
            "status": "error"
        } 