from typing import TypedDict, List, Optional, Dict, Literal, Any, Union
from datetime import datetime, UTC
import logging
import uuid
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Message(TypedDict):
    role: str  # "host" or username from livestream
    content: str
    timestamp: datetime
    interaction_type: str  # "local_agent" or "livestream"
    session_id: str

class Session(TypedDict):
    session_id: str
    messages: List[Message]
    created_at: datetime
    last_updated: datetime
    metadata: Optional[dict]

class ContextConfiguration(TypedDict):
    session_id: str
    latest_summary: Optional[dict]  # The most recent summary message
    active_message_ids: List[str]   # IDs of messages in current context
    last_updated: datetime

class OperationStatus(Enum):
    PENDING = "pending"          # Item is waiting for action
    APPROVED = "approved"        # Item has been approved
    REJECTED = "rejected"        # Item was rejected
    SCHEDULED = "scheduled"      # Item is scheduled for execution
    EXECUTED = "executed"        # Item has been executed
    FAILED = "failed"           # Item execution failed

class ToolOperationState(Enum):
    INACTIVE = "inactive"
    COLLECTING = "collecting"     # Tool is generating/collecting items
    APPROVING = "approving"       # Items are being reviewed
    EXECUTING = "executing"       # Approved items are being executed
    COMPLETED = "completed"       # Operation is finished
    ERROR = "error"              # Operation encountered error
    CANCELLED = "cancelled"      # Operation was cancelled

class ContentType(str, Enum):
    """Types of content that can be produced"""
    TWEET = "tweet"
    CALENDAR = "calendar"
    PROMPT = "system_prompt"
    SEARCH_RESULT = "search_result"

class ToolType(str, Enum):
    """Types of tools available"""
    TWEET_SCRAPER = "tweet_scraper"
    PROMPT_ENGINEER = "prompt_engineer"
    WEB_SEARCH = "web_search"
    TWITTER = "twitter"
    CALENDAR = "calendar"

class WorkflowOperation(TypedDict):
    """Top-level workflow operation"""
    workflow_id: str
    session_id: str
    status: str  # Maps to OperationStatus
    created_at: datetime
    last_updated: datetime
    tool_sequence: List[str]  # List of tool_operation_ids in order
    dependencies: Dict[str, List[str]]  # tool_id -> [dependent_tool_ids]
    metadata: Dict[str, Any]

class ScheduledOperation(TypedDict):
    """Base class for any scheduled operation or content"""
    session_id: str
    workflow_id: Optional[str]  # Link to parent workflow if part of one
    tool_operation_id: Optional[str]  # Link to tool operation that created this
    content_type: str  # Maps to ContentType
    status: str  # Maps to OperationStatus
    count: int  # Number of items to schedule (tweets, posts, etc)
    schedule_type: Literal["one_time", "multiple", "recurring"]  # Type of schedule
    schedule_time: str  # When to execute
    approval_required: bool  # Whether approval is needed
    content: Dict[str, Any]  # The actual content to be executed
    pending_items: List[str]  # IDs of items pending approval
    approved_items: List[str]  # IDs of approved items
    rejected_items: List[str]  # IDs of rejected items
    created_at: datetime
    scheduled_time: Optional[datetime]
    executed_time: Optional[datetime]
    metadata: Dict[str, Any]
    retry_count: int
    last_error: Optional[str]

class ToolItemContent(TypedDict):
    """Base content structure for all tools"""
    raw_content: str
    formatted_content: Optional[str]
    references: Optional[List[str]]
    version: str

class ToolItemParams(TypedDict):
    """Base parameters for all tools"""
    schedule_time: Optional[datetime]
    retry_policy: Optional[Dict]
    execution_window: Optional[Dict]

class ToolItemMetadata(TypedDict):
    """Base metadata for all tools"""
    generated_at: str
    generated_by: str
    last_modified: str
    version: str

class ToolItemResponse(TypedDict):
    """Base API response for all tools"""
    success: bool
    timestamp: str
    platform_id: Optional[str]
    error: Optional[str]

class OperationMetadata(TypedDict):
    """Standard metadata for operations"""
    content_type: str
    original_request: Optional[str]
    generated_at: str
    execution_time: Optional[str]
    retry_count: int
    last_error: Optional[str]

class ToolExecution(TypedDict):
    """Individual tool execution record"""
    tool_operation_id: str           # Reference to tool_operations
    session_id: str
    tool_type: str             # Maps to ToolType
    state: str                 # Maps to ToolOperationState
    parameters: Dict[str, Any] # Tool-specific parameters
    result: Optional[Dict[str, Any]]
    created_at: datetime
    last_updated: datetime
    metadata: OperationMetadata
    retry_count: int
    last_error: Optional[str]

class ToolItem(TypedDict):
    """Generic tool item"""
    session_id: str
    workflow_id: Optional[str]
    tool_operation_id: str
    content_type: str
    state: str
    status: str
    content: ToolItemContent
    parameters: ToolItemParams
    metadata: ToolItemMetadata
    api_response: Optional[ToolItemResponse]
    created_at: datetime
    scheduled_time: Optional[datetime]
    executed_time: Optional[datetime]
    posted_time: Optional[datetime]
    schedule_id: str
    execution_id: Optional[str]
    retry_count: int
    last_error: Optional[str]

class ToolOperation(TypedDict):
    """Individual tool operation with workflow support"""
    session_id: str
    tool_type: str              # Maps to ToolType enum
    state: str                  # Maps to ToolOperationState
    step: str
    workflow_id: Optional[str]  # Link to parent workflow
    workflow_step: Optional[int] # Order in workflow sequence
    input_data: Dict[str, Any]  # Data from previous tools
    output_data: Dict[str, Any] # Data produced by this tool
    metadata: OperationMetadata # Standard metadata including content_type
    created_at: datetime
    last_updated: datetime
    end_reason: Optional[str]

class TwitterContent(ToolItemContent):
    """Twitter-specific content structure"""
    thread_structure: Optional[List[str]]
    mentions: Optional[List[str]]
    hashtags: Optional[List[str]]
    urls: Optional[List[str]]

class TwitterParams(ToolItemParams):
    """Twitter-specific parameters"""
    account_id: Optional[str]
    media_files: Optional[List[str]]
    poll_options: Optional[List[str]]
    poll_duration: Optional[int]
    reply_settings: Optional[str]
    quote_tweet_id: Optional[str]

class TwitterMetadata(ToolItemMetadata):
    """Twitter-specific metadata"""
    estimated_engagement: str
    audience_targeting: Optional[Dict]
    content_category: Optional[str]
    sensitivity_level: Optional[str]

class TwitterResponse(ToolItemResponse):
    """Twitter-specific API response"""
    tweet_id: str
    engagement_metrics: Optional[Dict]
    visibility_stats: Optional[Dict]

class Tweet(ToolItem):
    """Tweet implementation of ToolItem"""
    content: TwitterContent
    parameters: TwitterParams
    metadata: TwitterMetadata
    api_response: Optional[TwitterResponse]

class TwitterCommandAnalysis(BaseModel):
    tools_needed: List[Dict[str, Any]]
    reasoning: str

class TweetGenerationResponse(BaseModel):
    items: List[Dict[str, Any]]

class RinDB:
    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client['rin_multimodal']
        # Legacy collections for migration
        self.tweets = self.db['rin.tweets']
        self.tweet_schedules = self.db['rin.tweet_schedules']
        
        # Current collections
        self.messages = self.db['rin.messages']
        self.context_configs = self.db['rin.context_configs']
        self.tool_items = self.db['rin.tool_items']
        self.tool_operations = self.db['rin.tool_operations']
        self.tool_executions = self.db['rin.tool_executions']
        self.scheduled_operations = self.db['rin.scheduled_operations']
        self._initialized = False
        logger.info(f"Connected to database: {self.db.name}")

    async def initialize(self):
        """Initialize database and collections"""
        try:
            collections = await self.db.list_collection_names()
            
            # Create collections if they don't exist
            required_collections = [
                'rin.messages',
                'rin.context_configs',
                'rin.tool_items',
                'rin.tool_operations',
                'rin.tool_executions',
                'rin.scheduled_operations'
            ]
            
            for collection in required_collections:
                if collection not in collections:
                    await self.db.create_collection(collection)
                    logger.info(f"Created {collection} collection")
            
            # Setup indexes
            await self._setup_indexes()
            self._initialized = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def is_initialized(self) -> bool:
        """Check if database is properly initialized"""
        try:
            collections = await self.db.list_collection_names()
            required_collections = [
                'rin.messages',
                'rin.context_configs',
                'rin.tool_items',
                'rin.tool_operations',
                'rin.tool_executions',
                'rin.scheduled_operations'
            ]
            
            has_collections = all(col in collections for col in required_collections)
            
            if not has_collections:
                logger.warning("Required collections not found")
                return False
                
            await self.db.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    async def _setup_indexes(self):
        """Setup indexes for Rin collections"""
        try:
            # Message and context indexes
            await self.messages.create_index([("session_id", 1)])
            await self.messages.create_index([("timestamp", 1)])
            await self.context_configs.create_index([("session_id", 1)])

            # Tool operations indexes
            await self.tool_operations.create_index([("session_id", 1)])
            await self.tool_operations.create_index([("state", 1)])
            await self.tool_operations.create_index([("tool_type", 1)])
            await self.tool_operations.create_index([("last_updated", 1)])
            
            # Tool executions tracking
            await self.tool_executions.create_index([("tool_operation_id", 1)])
            await self.tool_executions.create_index([("session_id", 1)])
            await self.tool_executions.create_index([("state", 1)])
            await self.tool_executions.create_index([("created_at", 1)])
            
            # Tool items (content)
            await self.tool_items.create_index([("session_id", 1)])
            await self.tool_items.create_index([("content_type", 1)])
            await self.tool_items.create_index([("status", 1)])
            await self.tool_items.create_index([("state", 1)])
            await self.tool_items.create_index([("schedule_id", 1)])
            await self.tool_items.create_index([("tool_operation_id", 1)])

            # Temporal indexes
            await self.tool_items.create_index([("created_at", 1)])
            await self.tool_items.create_index([("scheduled_time", 1)])
            await self.tool_items.create_index([("posted_time", 1)])

            # Compound indexes for common queries
            await self.tool_items.create_index([
                ("tool_operation_id", 1),
                ("state", 1)
            ])
            await self.tool_items.create_index([
                ("tool_operation_id", 1),
                ("status", 1)
            ])
            
            # Scheduled operations indexes
            await self.scheduled_operations.create_index([("session_id", 1)])
            await self.scheduled_operations.create_index([("status", 1)])
            await self.scheduled_operations.create_index([("scheduled_time", 1)])
            await self.scheduled_operations.create_index([("content_type", 1)])
            await self.scheduled_operations.create_index([
                ("status", 1),
                ("scheduled_time", 1)
            ])

            logger.info("Successfully created database indexes")
        except Exception as e:
            logger.error(f"Error setting up indexes: {str(e)}")
            raise

    async def add_message(self, session_id: str, role: str, content: str, 
                         interaction_type: str = 'local_agent', metadata: Optional[dict] = None):
        """Add a message to the database
        
        Args:
            session_id: Unique session identifier
            role: Either "host" for local input or username for livestream
            content: Message content
            interaction_type: Either "local_agent" or "livestream"
            metadata: Optional additional metadata
        """
        message = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "interaction_type": interaction_type
        }
        if metadata:
            message["metadata"] = metadata
            
        await self.messages.insert_one(message)
        return message

    async def get_session_messages(self, session_id: str):
        cursor = self.messages.find({"session_id": session_id}).sort("timestamp", 1)
        return await cursor.to_list(length=None)

    async def clear_session(self, session_id: str):
        await self.messages.delete_many({"session_id": session_id})


    async def update_session_metadata(self, session_id: str, metadata: dict):
        """Update or create session metadata"""
        try:
            await self.messages.update_many(
                {"session_id": session_id},
                {"$set": {"metadata": metadata}},
                upsert=True
            )
            logger.info(f"Updated metadata for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update session metadata: {e}")
            return False

    async def add_context_summary(self, session_id: str, summary: dict, active_message_ids: List[str]):
        """Update context configuration with new summary"""
        await self.context_configs.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "latest_summary": summary,
                    "active_message_ids": active_message_ids,
                    "last_updated": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def get_context_configuration(self, session_id: str) -> Optional[ContextConfiguration]:
        """Get current context configuration"""
        return await self.context_configs.find_one({"session_id": session_id})

    async def get_messages_by_ids(self, session_id: str, message_ids: List[str]) -> List[Message]:
        """Get specific messages by their IDs"""
        cursor = self.messages.find({
            "session_id": session_id,
            "_id": {"$in": [ObjectId(id) for id in message_ids]}
        }).sort("timestamp", 1)
        return await cursor.to_list(length=None)

    async def create_tool_item(
        self,
        session_id: str,
        content_type: str,
        content: Dict,
        parameters: Dict,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a new tool item with validation"""
        try:
            # Validate required content
            if not content.get('raw_content'):
                raise ValueError("Tool item content cannot be empty")

            tool_item = {
                "session_id": session_id,
                "content_type": content_type,
                "status": OperationStatus.PENDING.value,
                "content": {
                    **content,
                    "version": "1.0"
                },
                "parameters": {
                    **parameters,
                    "retry_policy": parameters.get("retry_policy", {"max_attempts": 3, "delay": 300})
                },
                "metadata": {
                    **(metadata or {}),
                    "generated_at": datetime.now(UTC).isoformat(),
                    "generated_by": "system",
                    "last_modified": datetime.now(UTC).isoformat(),
                    "version": "1.0"
                },
                "created_at": datetime.now(UTC),
                "retry_count": 0
            }

            result = await self.tool_items.insert_one(tool_item)
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Error creating tool item: {e}")
            raise

    async def get_pending_items(self, 
                              content_type: Optional[str] = None,
                              schedule_id: Optional[str] = None) -> List[Dict]:
        """Get pending items, optionally filtered by type and schedule"""
        try:
            query = {"status": OperationStatus.PENDING.value}
            if content_type:
                query["content_type"] = content_type
            if schedule_id:
                query["schedule_id"] = schedule_id
            
            cursor = self.tool_items.find(query)
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error fetching pending items: {e}")
            return []

    async def update_tool_item_status(self, 
                                    item_id: str, 
                                    status: OperationStatus,
                                    api_response: Optional[Dict] = None,
                                    error: Optional[str] = None,
                                    metadata: Optional[Dict] = None) -> bool:
        """Update tool item status and related fields"""
        try:
            update_data = {
                "status": status.value if isinstance(status, OperationStatus) else status,
                "last_updated": datetime.now(UTC)
            }
            
            if status == OperationStatus.EXECUTED and api_response:
                update_data["executed_time"] = datetime.now(UTC)
                update_data["api_response"] = api_response
            
            if error:
                update_data["last_error"] = error
            
            if metadata:
                update_data["metadata"] = {
                    **update_data.get("metadata", {}),
                    **metadata
                }
            
            result = await self.tool_items.update_one(
                {"_id": ObjectId(item_id)},
                {
                    "$set": update_data,
                    "$inc": {"retry_count": 1} if error else {}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating tool item status: {e}")
            return False

    async def set_tool_operation_state(self, session_id: str, operation_data: Dict) -> Optional[Dict]:
        """Set tool operation state"""
        try:
            # Ensure required fields
            operation_data.update({
                "last_updated": datetime.now(UTC)
            })
            
            # Handle both new operations and updates
            result = await self.tool_operations.find_one_and_update(
                {"session_id": session_id},
                {"$set": operation_data},
                upsert=True,
                return_document=True
            )
            
            if result:
                logger.info(f"Set operation state for session {session_id}")
                return result
            else:
                logger.error(f"Failed to set operation state for session {session_id}")
                return None

        except Exception as e:
            logger.error(f"Error setting operation state: {e}")
            return None

    async def get_tool_operation_state(self, session_id: str) -> Optional[Dict]:
        """Get tool operation state"""
        try:
            return await self.tool_operations.find_one({"session_id": session_id})
        except Exception as e:
            logger.error(f"Error getting operation state: {e}")
            return None

    async def get_scheduled_operation(self, tool_operation_id: str) -> Optional[Dict]:
        """Get scheduled operation by ID"""
        try:
            # First try direct ObjectId lookup
            if ObjectId.is_valid(tool_operation_id):
                schedule = await self.scheduled_operations.find_one({"_id": ObjectId(tool_operation_id)})
                if schedule:
                    logger.info(f"Found schedule by ObjectId: {tool_operation_id}")
                    return schedule

            # Try session_id or tool_operation_id lookup
            schedule = await self.scheduled_operations.find_one({
                "$or": [
                    {"session_id": tool_operation_id},
                    {"tool_operation_id": tool_operation_id}
                ]
            })
            
            if schedule:
                logger.info(f"Found schedule by session/operation ID: {tool_operation_id}")
                return schedule
            
            logger.warning(f"No schedule found for ID: {tool_operation_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting scheduled operation: {e}")
            return None

    async def create_scheduled_operation(self, 
                                session_id: str,
                                tool_operation_id: str,
                                content_type: str,
                                count: int,
                                schedule_type: str,
                                schedule_time: str,
                                content: Dict,
                                metadata: Optional[Dict] = None) -> str:
        """Create new scheduled operation with proper schema"""
        try:
            operation = {
                "session_id": session_id,
                "tool_operation_id": tool_operation_id,
                "content_type": content_type,
                "status": OperationStatus.PENDING.value,
                "count": count,
                "schedule_type": schedule_type,
                "schedule_time": schedule_time,
                "approval_required": True,
                "content": content,
                "pending_items": [],
                "approved_items": [],
                "rejected_items": [],
                "created_at": datetime.now(UTC),
                "metadata": {
                    **(metadata or {}),
                    "content_type": content_type,
                    "created_at": datetime.now(UTC).isoformat()
                },
                "retry_count": 0
            }

            result = await self.scheduled_operations.insert_one(operation)
            logger.info(f"Created scheduled operation: {result.inserted_id}")
            
            # Return the created schedule
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Error creating scheduled operation: {e}")
            raise

    async def delete_all_scheduled_tweets(self):
        """Delete all tweet schedules and their associated tweets"""
        try:
            # Get all schedule IDs first
            schedule_cursor = self.scheduled_operations.find({})
            schedules = await schedule_cursor.to_list(length=None)
            schedule_ids = [str(schedule['_id']) for schedule in schedules]
            
            # Delete all tweets associated with these schedules
            for schedule_id in schedule_ids:
                await self.tool_items.delete_many({"schedule_id": schedule_id})
                logger.info(f"Deleted items for schedule {schedule_id}")
            
            # Delete all tweet schedules
            result = await self.scheduled_operations.delete_many({})
            
            logger.info(f"Deleted {result.deleted_count} scheduled operations")
            return {
                "operations_deleted": result.deleted_count,
                "schedule_ids": schedule_ids
            }
            
        except Exception as e:
            logger.error(f"Error deleting scheduled operations: {e}")
            raise

    async def update_scheduled_operation(
        self,
        schedule_id: str,
        status: Optional[str] = None,
        pending_item_ids: Optional[List[str]] = None,
        approved_item_ids: Optional[List[str]] = None,
        rejected_item_ids: Optional[List[str]] = None,
        schedule_info: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Update scheduled operation with new data"""
        try:
            update_data = {"last_updated": datetime.now(UTC)}
            
            if status:
                update_data["status"] = status
                
            if pending_item_ids is not None:
                update_data["pending_items"] = pending_item_ids
                
            if approved_item_ids is not None:
                update_data["approved_items"] = approved_item_ids
                
            if rejected_item_ids is not None:
                update_data["rejected_items"] = rejected_item_ids
                
            if schedule_info:
                update_data["schedule_info"] = schedule_info
                
            if metadata:
                update_data["metadata"] = {
                    "$set": {
                        **update_data.get("metadata", {}),
                        **metadata,
                        "last_modified": datetime.now(UTC).isoformat()
                    }
                }

            result = await self.scheduled_operations.update_one(
                {"_id": ObjectId(schedule_id) if ObjectId.is_valid(schedule_id) else schedule_id},
                {"$set": update_data}
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Updated scheduled operation: {schedule_id}")
            else:
                logger.warning(f"No scheduled operation updated for ID: {schedule_id}")
                
            return success

        except Exception as e:
            logger.error(f"Error updating scheduled operation: {e}")
            return False