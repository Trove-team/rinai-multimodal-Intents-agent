import pytest
import os
import sys
from pathlib import Path
from datetime import datetime, UTC
from dotenv import load_dotenv
from bson.objectid import ObjectId
from typing import List, Dict
import asyncio
import logging

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# Load environment variables before imports
load_dotenv(dotenv_path=Path(project_root) / '.env')

from src.tools.post_tweets import TwitterTool
from src.tools.base import AgentDependencies
from src.managers.tool_state_manager import ToolStateManager
from src.services.llm_service import LLMService
from src.managers.approval_manager import ApprovalManager
from src.db.mongo_manager import MongoManager
from src.db.enums import ToolOperationState, OperationStatus, ApprovalState
from src.db.db_schema import ToolOperation

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # This ensures our config takes precedence
)

@pytest.fixture(autouse=True)
async def setup_teardown():
    """Setup and teardown for all tests"""
    # Setup
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    await MongoManager.initialize(mongo_uri)
    
    yield
    
    # Teardown
    try:
        db = MongoManager.get_db()
        await db.scheduled_operations.delete_many({})
        await db.tool_operations.delete_many({})
        await db.tweets.delete_many({})
    finally:
        await MongoManager.close()

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_tweet_tool_workflow():
    """Test complete tweet tool workflow"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    await MongoManager.initialize(mongo_uri)
    db = MongoManager.get_db()
    
    try:
        # 1. Setup
        deps = AgentDependencies(
            session_id="test_workflow_session",
            user_id="test_user_123",
            context={},
            tools_available=["twitter"]
        )
        
        tool_state_manager = ToolStateManager(db=db)
        llm_service = LLMService()
        approval_manager = ApprovalManager(
            tool_state_manager=tool_state_manager,
            db=db,
            llm_service=llm_service
        )
        
        tweet_tool = TwitterTool(
            deps=deps,
            tool_state_manager=tool_state_manager,
            llm_service=llm_service,
            approval_manager=approval_manager
        )

        # 2. Initial Command - Analysis and Generation
        initial_command = "Generate 2 tweets about AI"
        result = await tweet_tool.run(initial_command)
        
        # Verify items were generated
        items = result.get('data', {}).get('items', [])
        assert len(items) > 0, "No items returned in approval flow"
        
        # 3. Approval Response
        approval_response = "Yes, these look good"
        approval_result = await tweet_tool.run(approval_response)
        
        logger.info("Tweet tool workflow test completed successfully")
        
    except Exception as e:
        logger.error(f"Test error in workflow: {e}")
        raise
        
    finally:
        # Cleanup
        await db.scheduled_operations.delete_many({"session_id": deps.session_id})
        await db.tool_operations.delete_many({"session_id": deps.session_id})
        await db.tool_items.delete_many({"session_id": deps.session_id})
        await MongoManager.close()

@pytest.mark.asyncio
async def test_tweet_tool_cancellation():
    """Test cancellation of tweet tool workflow"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    await MongoManager.initialize(mongo_uri)
    db = MongoManager.get_db()
    
    try:
        # Setup
        deps = AgentDependencies(
            session_id="test_cancel_session",
            user_id="test_user_123",
            context={},
            tools_available=["twitter"]
        )
        
        tool_state_manager = ToolStateManager(db=db)
        llm_service = LLMService()
        approval_manager = ApprovalManager(
            tool_state_manager=tool_state_manager,
            db=db,
            llm_service=llm_service
        )
        
        tweet_tool = TwitterTool(
            deps=deps,
            tool_state_manager=tool_state_manager,
            llm_service=llm_service,
            approval_manager=approval_manager
        )

        # Initial command and verify items created
        initial_command = "Generate 2 tweets about AI"
        result = await tweet_tool.run(initial_command)
        assert result.get('data', {}).get('items'), "No items returned for approval"
        
        # Send cancellation
        cancel_response = "cancel"
        cancel_result = await tweet_tool.run(cancel_response)
        
        logger.info("Tweet tool cancellation test completed successfully")
        
    except Exception as e:
        logger.error(f"Test error in cancellation: {e}")
        raise
        
    finally:
        # Cleanup
        await db.scheduled_operations.delete_many({"session_id": deps.session_id})
        await db.tool_operations.delete_many({"session_id": deps.session_id})
        await db.tool_items.delete_many({"session_id": deps.session_id})
        await MongoManager.close()

@pytest.mark.asyncio
async def test_analyze_twitter_command():
    """Test just the command analysis function"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    await MongoManager.initialize(mongo_uri)
    db = MongoManager.get_db()
    
    try:
        # Setup
        logger.info("Setting up test dependencies...")
        deps = AgentDependencies(
            session_id="test_analysis_session",
            user_id="test_user_123",
            context={},
            tools_available=["twitter"]
        )
        
        tool_state_manager = ToolStateManager(db=db)
        llm_service = LLMService()
        approval_manager = ApprovalManager(
            tool_state_manager=tool_state_manager,
            db=db,
            llm_service=llm_service
        )
        
        logger.info("Initializing tweet tool...")
        tweet_tool = TwitterTool(
            deps=deps,
            tool_state_manager=tool_state_manager,
            llm_service=llm_service,
            approval_manager=approval_manager
        )

        # Test command analysis
        command = "Generate 2 tweets about AI"
        logger.info(f"Testing command analysis with: {command}")
        result = await tweet_tool._analyze_twitter_command(command)
        
        # Verify result structure
        assert result is not None, "Analysis result is None"
        assert "schedule_id" in result, "No schedule_id in result"
        assert "topic" in result, "No topic in result"
        assert "item_count" in result, "No item_count in result"
        
        logger.info("Command analysis test completed successfully")
        
    except Exception as e:
        logger.error(f"Test error in command analysis: {e}")
        raise
        
    finally:
        # Cleanup
        await db.scheduled_operations.delete_many({"session_id": deps.session_id})
        await db.tool_operations.delete_many({"session_id": deps.session_id})
        await MongoManager.close()

@pytest.mark.asyncio
async def test_tweet_tool_partial_approval():
    """Test partial approval and regeneration workflow"""
    try:
        # Setup (same as before)
        deps = setup_test_dependencies()
        tweet_tool = setup_tweet_tool(deps)
        
        # 1. Initial generation
        initial_result = await tweet_tool.run("Generate 2 tweets about AI")
        tool_operation_id = initial_result.get('data', {}).get('tool_operation_id')
        
        # 2. Partial approval - approve one, reject one
        partial_result = await tweet_tool.run("approve item 1, regenerate item 2")
        
        # Verify states after partial approval
        approved_items = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.EXECUTING.value
        }).to_list(None)
        assert len(approved_items) == 1, "Expected 1 approved item"
        
        rejected_items = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.COMPLETED.value,
            "status": OperationStatus.REJECTED.value
        }).to_list(None)
        assert len(rejected_items) == 1, "Expected 1 rejected item"
        
        # 3. Full approval of regenerated item
        final_result = await tweet_tool.run("approve all")
        
        # Verify final states
        final_approved = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.EXECUTING.value
        }).to_list(None)
        assert len(final_approved) == 2, "Expected 2 items in EXECUTING state"
        
        # Verify operation completed
        final_op = await tool_state_manager.get_operation(deps.session_id)
        assert final_op['state'] == ToolOperationState.EXECUTING.value
        
    finally:
        # Cleanup
        await cleanup_test_data(deps)

@pytest.mark.asyncio
async def test_tweet_tool_multiple_regeneration():
    """Test regeneration of multiple items workflow"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    await MongoManager.initialize(mongo_uri)
    db = MongoManager.get_db()
    
    try:
        # 1. Setup
        deps = AgentDependencies(
            session_id="test_multiple_regen_session",
            user_id="test_user_123",
            context={},
            tools_available=["twitter"]
        )
        
        tool_state_manager = ToolStateManager(db=db)
        llm_service = LLMService()
        approval_manager = ApprovalManager(
            tool_state_manager=tool_state_manager,
            db=db,
            llm_service=llm_service
        )
        
        tweet_tool = TwitterTool(
            deps=deps,
            tool_state_manager=tool_state_manager,
            llm_service=llm_service,
            approval_manager=approval_manager
        )

        # 2. Initial generation
        initial_result = await tweet_tool.run("Generate 3 tweets about AI")
        operation = await tool_state_manager.get_operation(deps.session_id)
        tool_operation_id = str(operation['_id'])
        
        # 3. Partial Approval - approve one, reject two
        partial_approval = "approve item 1, regenerate items 2 and 3"
        approval_result = await tweet_tool.run(partial_approval)
        
        # Verify first-turn states
        approved_items = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.EXECUTING.value,
            "status": OperationStatus.APPROVED.value
        }).to_list(None)
        assert len(approved_items) == 1, "Expected 1 approved item"
        
        rejected_items = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.COMPLETED.value,
            "status": OperationStatus.REJECTED.value
        }).to_list(None)
        assert len(rejected_items) == 2, "Expected 2 rejected items"
        
        # The regenerated items should be in an approval flow
        assert approval_result.get('approval_state') == ApprovalState.AWAITING_APPROVAL.value
        assert len(approval_result.get('data', {}).get('items', [])) == 2, "Expected 2 new items for approval"
        
        # 4. Second turn - approve the regenerated items
        second_approval = "approve all"
        final_result = await tweet_tool.run(second_approval)
        
        # Verify all items are now approved
        final_approved = await db.tool_items.find({
            "tool_operation_id": tool_operation_id,
            "state": ToolOperationState.EXECUTING.value,
            "status": OperationStatus.APPROVED.value
        }).to_list(None)
        assert len(final_approved) == 3, "Expected all 3 items to be approved (1 from first turn + 2 from second)"
        
        # Verify operation completed successfully
        final_op = await tool_state_manager.get_operation_by_id(tool_operation_id)
        assert final_op['state'] == ToolOperationState.EXECUTING.value, "Operation should be in EXECUTING state"
        
        logger.info("Tweet tool multiple regeneration test completed successfully")
        
    except Exception as e:
        logger.error(f"Test error in multiple regeneration: {e}")
        raise
        
    finally:
        # Cleanup
        await db.scheduled_operations.delete_many({"session_id": deps.session_id})
        await db.tool_operations.delete_many({"session_id": deps.session_id})
        await db.tool_items.delete_many({"session_id": deps.session_id})
        await MongoManager.close()

if __name__ == "__main__":
    pytest.main(["-v", "test_tweet_tool.py", "-s"]) 