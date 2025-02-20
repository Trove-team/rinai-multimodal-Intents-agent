from enum import Enum
from typing import Dict, Optional, Any, List
from datetime import datetime, UTC
import logging
from src.db.db_schema import RinDB, ToolOperation, ToolOperationState, OperationStatus
from src.utils.trigger_detector import TriggerDetector
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class ToolStateManager:
    def __init__(self, db: RinDB, schedule_service=None):
        """Initialize tool state manager with database connection"""
        logger.info("Initializing ToolStateManager...")
        if not db:
            logger.error("Database instance is None!")
            raise ValueError("Database instance is required")
        if not isinstance(db, RinDB):
            logger.error(f"Expected RinDB instance, got {type(db)}")
            raise ValueError(f"Database must be RinDB instance, got {type(db)}")
        self.db = db
        self.schedule_service = schedule_service
        self.operations = {}
        self.trigger_detector = TriggerDetector()  # Initialize the trigger detector
        logger.info("ToolStateManager initialized with database connection")

        # Updated state transitions to allow COLLECTING -> APPROVING
        self.valid_transitions = {
            ToolOperationState.INACTIVE.value: [
                ToolOperationState.COLLECTING.value
            ],
            ToolOperationState.COLLECTING.value: [
                ToolOperationState.APPROVING.value,
                ToolOperationState.ERROR.value,
                ToolOperationState.CANCELLED.value
            ],
            ToolOperationState.APPROVING.value: [
                ToolOperationState.EXECUTING.value,  # For approved items
                ToolOperationState.COLLECTING.value, # For items needing regeneration
                ToolOperationState.ERROR.value,
                ToolOperationState.CANCELLED.value
            ],
            ToolOperationState.EXECUTING.value: [
                ToolOperationState.COMPLETED.value,
                ToolOperationState.CANCELLED.value,
                ToolOperationState.ERROR.value
            ]
        }

    async def start_operation(
        self,
        session_id: str,
        operation_type: str,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Start any tool operation with a unique ID"""
        try:
            tool_operation_id = str(ObjectId())
            requires_approval = initial_data.get("requires_approval", True)
            
            operation_data = {
                "_id": ObjectId(tool_operation_id),
                "session_id": session_id,
                "tool_type": operation_type,
                "state": ToolOperationState.COLLECTING.value,
                "step": "analyzing",
                "input_data": {
                    "command": initial_data.get("command"),
                    "status": initial_data.get("status"),
                    "operation_metadata": initial_data.get("operation_metadata", {})
                },
                "output_data": {
                    "status": OperationStatus.PENDING.value,
                    "content": [],
                    "requires_approval": requires_approval,
                    "pending_items": [],
                    "approved_items": [],
                    "rejected_items": []
                },
                "metadata": {
                    "state_history": [{
                        "state": ToolOperationState.COLLECTING.value,
                        "step": "analyzing",
                        "timestamp": datetime.now(UTC).isoformat()
                    }],
                    "item_states": {}
                },
                "created_at": datetime.now(UTC),
                "last_updated": datetime.now(UTC)
            }
            
            # Create new operation
            result = await self.db.tool_operations.insert_one(operation_data)
            operation_data['_id'] = result.inserted_id
            logger.info(f"Started {operation_type} operation {tool_operation_id} for session {session_id}")
            return operation_data

        except Exception as e:
            logger.error(f"Error starting operation: {e}")
            return None

    async def update_operation(
        self,
        session_id: str,
        tool_operation_id: str,  # Now required
        state: str = None,
        step: str = None,
        metadata: Dict = None,
        content_updates: Dict = None
    ) -> bool:
        """Update tool operation state with operation ID"""
        try:
            # Fetch current operation by ID and session
            current_op = await self.db.tool_operations.find_one({
                "_id": ObjectId(tool_operation_id),
                "session_id": session_id
            })
            
            if not current_op:
                logger.error(f"No operation found for ID {tool_operation_id} and session {session_id}")
                return False

            # Build update data
            update_data = {"last_updated": datetime.now(UTC)}
            
            if state:
                current_state = current_op.get("state")
                if not self._is_valid_transition(current_state, state):
                    logger.warning(
                        f"Invalid state transition from {current_state} to {state}. "
                        f"Valid transitions are: {self.valid_transitions.get(current_state, [])}"
                    )
                    return False
                update_data["state"] = state
                
            if step:
                update_data["step"] = step

            if content_updates:
                # Merge with existing output_data
                existing_output = current_op.get("output_data", {})
                update_data["output_data"] = {
                    **existing_output,
                    **content_updates
                }

            if metadata:
                # Merge with existing metadata
                existing_metadata = current_op.get("metadata", {})
                update_data["metadata"] = {
                    **existing_metadata,
                    **metadata,
                    "last_modified": datetime.now(UTC).isoformat()
                }

            # Update operation by ID
            result = await self.db.tool_operations.find_one_and_update(
                {"_id": ObjectId(tool_operation_id)},
                {"$set": update_data},
                return_document=True
            )
            
            return bool(result)

        except Exception as e:
            logger.error(f"Error updating operation: {e}")
            return False

    async def get_operation(self, session_id: str) -> Optional[ToolOperation]:
        """Get current operation state"""
        return await self.db.get_tool_operation_state(session_id)

    async def end_operation(
        self,
        session_id: str,
        tool_operation_id: str,  # Now required
        status: OperationStatus,
        reason: str = None,
        api_response: Dict = None,
        requires_approval: bool = True,
        is_scheduled: bool = False,
        metadata: Dict = None
    ) -> bool:
        """End operation with proper state transition"""
        try:
            current_op = await self.db.tool_operations.find_one({
                "_id": ObjectId(tool_operation_id),
                "session_id": session_id
            })
            
            if not current_op:
                return False

            current_state = current_op.get("state")
            final_state = self._get_final_state(current_state, status)

            # Update operation with final state
            operation_data = {
                "state": final_state,
                "step": self._get_step_for_state(final_state),
                "output_data": {
                    **(current_op.get("output_data", {})),
                    "status": status.value,
                    "api_response": api_response
                },
                "metadata": {
                    **(current_op.get("metadata", {})),
                    "end_time": datetime.now(UTC).isoformat(),
                    "end_reason": reason,
                    "final_status": status.value,
                    "requires_approval": requires_approval,
                    "is_scheduled": is_scheduled
                },
                "last_updated": datetime.now(UTC)
            }

            return await self.update_operation(
                session_id=session_id,
                tool_operation_id=tool_operation_id,
                state=final_state,
                metadata=operation_data.get("metadata", {})
            )

        except Exception as e:
            logger.error(f"Error ending operation: {e}")
            return False

    def _is_valid_transition(self, current_state: str, new_state: str) -> bool:
        """Check if state transition is valid"""
        try:
            # Normalize states to lowercase for comparison
            current = current_state.lower() if current_state else 'inactive'
            new = new_state.lower() if new_state else 'inactive'
            
            # Get valid transitions for current state
            valid_transitions = self.valid_transitions.get(current, [])
            
            if new not in valid_transitions:
                logger.warning(
                    f"Invalid state transition attempted: {current} -> {new}. "
                    f"Valid transitions are: {valid_transitions}"
                )
                return False
            
            logger.info(f"Valid state transition: {current} -> {new}")
            return True
        
        except Exception as e:
            logger.error(f"Error checking state transition: {e}")
            return False

    def _get_step_for_state(self, state: ToolOperationState) -> str:
        """Get appropriate step name for state"""
        step_mapping = {
            ToolOperationState.INACTIVE: "inactive",
            ToolOperationState.COLLECTING: "collecting",
            ToolOperationState.APPROVING: "awaiting_approval",
            ToolOperationState.EXECUTING: "executing",
            ToolOperationState.COMPLETED: "completed",
            ToolOperationState.CANCELLED: "cancelled",
            ToolOperationState.ERROR: "error"
        }
        return step_mapping.get(state, "unknown")

    def _get_final_state(self, current_state: str, status: OperationStatus) -> str:
        """Determine final state based on current state and status"""
        if status == OperationStatus.APPROVED:
            return ToolOperationState.COMPLETED.value
        elif status == OperationStatus.FAILED:
            return ToolOperationState.ERROR.value
        elif status == OperationStatus.REJECTED:
            return ToolOperationState.CANCELLED.value
        else:
            logger.warning(f"Unhandled status {status} in state {current_state}")
            return ToolOperationState.ERROR.value

    async def get_operation_state(self, session_id: str) -> Optional[Dict]:
        """Get current operation state"""
        try:
            return await self.db.get_tool_operation_state(session_id)
        except Exception as e:
            logger.error(f"Error getting operation state: {e}")
            return None

    async def validate_operation_items(self, tool_operation_id: str) -> bool:
        """Validate all items are properly linked to operation"""
        try:
            operation = await self.db.tool_operations.find_one({"_id": ObjectId(tool_operation_id)})
            if not operation:
                return False

            # Get all items for this operation
            items = await self.db.tool_items.find({
                "tool_operation_id": tool_operation_id
            }).to_list(None)

            # Validate items match operation's pending_items
            pending_ids = set(operation["output_data"]["pending_items"])
            item_ids = {str(item["_id"]) for item in items}
            
            if pending_ids != item_ids:
                logger.error(f"Mismatch in operation items. Expected: {pending_ids}, Found: {item_ids}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating operation items: {e}")
            return False

    async def get_operation_by_id(self, tool_operation_id: str) -> Optional[Dict]:
        """Get operation by ID"""
        try:
            operation = await self.db.tool_operations.find_one({"_id": ObjectId(tool_operation_id)})
            return operation
        except Exception as e:
            logger.error(f"Error getting operation by ID: {e}")
            return None

    async def update_operation_items(
        self,
        tool_operation_id: str,
        item_ids: List[str],
        new_state: str,
        new_status: str
    ) -> bool:
        """Update state and status for specific items in an operation"""
        try:
            result = await self.db.tool_items.update_many(
                {
                    "_id": {"$in": [ObjectId(id) for id in item_ids]},
                    "tool_operation_id": tool_operation_id
                },
                {
                    "$set": {
                        "state": new_state,
                        "status": new_status,
                        "last_updated": datetime.now(UTC)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating operation items: {e}")
            return False

    async def get_operation_items(
        self,
        tool_operation_id: str,
        state: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Get items for an operation with optional state/status filters"""
        try:
            query = {"tool_operation_id": tool_operation_id}
            if state:
                query["state"] = state
            if status:
                query["status"] = status
            
            return await self.db.tool_items.find(query).to_list(None)
        except Exception as e:
            logger.error(f"Error getting operation items: {e}")
            return []

    async def update_operation_state(
        self,
        tool_operation_id: str,
        item_updates: Optional[List[Dict]] = None
    ) -> bool:
        """Update operation status based on aggregate item states"""
        try:
            operation = await self.get_operation_by_id(tool_operation_id)
            if not operation:
                return False

            # Get all items if no updates provided
            items = item_updates or await self.get_operation_items(tool_operation_id)
            
            # Get unique item states
            item_states = {item["state"] for item in items}
            
            # Determine operation status based on item states
            new_status = self._determine_operation_status(item_states)
            
            if new_status != operation.get("status"):
                # Update all items to match new operation status
                await self.sync_items_to_operation_status(tool_operation_id, new_status)
                
                # Update operation
                await self.db.tool_operations.update_one(
                    {"_id": ObjectId(tool_operation_id)},
                    {
                        "$set": {
                            "status": new_status,
                            "last_updated": datetime.now(UTC)
                        }
                    }
                )
            return True

        except Exception as e:
            logger.error(f"Error updating operation state: {e}")
            return False

    def _determine_operation_status(self, item_states: set) -> str:
        """Determine operation status based on item states"""
        # If any items are still processing, operation remains PENDING
        if any(state in {
            ToolOperationState.COLLECTING.value,
            ToolOperationState.APPROVING.value,
            ToolOperationState.EXECUTING.value
        } for state in item_states):
            return OperationStatus.PENDING.value
            
        # All items must be in the same final state
        if all(state == ToolOperationState.COMPLETED.value for state in item_states):
            return OperationStatus.EXECUTED.value
        elif all(state == ToolOperationState.CANCELLED.value for state in item_states):
            return OperationStatus.REJECTED.value
        elif all(state == ToolOperationState.ERROR.value for state in item_states):
            return OperationStatus.FAILED.value
            
        # Default to PENDING if mixed states
        return OperationStatus.PENDING.value

    async def sync_items_to_operation_status(
        self,
        tool_operation_id: str,
        operation_status: str
    ) -> None:
        """Sync all items to match operation status"""
        status_to_state_map = {
            OperationStatus.APPROVED.value: ToolOperationState.EXECUTING.value,
            OperationStatus.SCHEDULED.value: ToolOperationState.EXECUTING.value,
            OperationStatus.EXECUTED.value: ToolOperationState.COMPLETED.value,
            OperationStatus.REJECTED.value: ToolOperationState.CANCELLED.value,
            OperationStatus.FAILED.value: ToolOperationState.ERROR.value
        }
        
        if operation_status in status_to_state_map:
            new_state = status_to_state_map[operation_status]
            await self.db.tool_items.update_many(
                {"tool_operation_id": tool_operation_id},
                {
                    "$set": {
                        "state": new_state,
                        "last_updated": datetime.now(UTC)
                    }
                }
            )