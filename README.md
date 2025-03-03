# RinAI Multimodal V-Tuber & Desktop Agent

![RinAI Multimodal UX](https://github.com/dleerdefi/rinai-multimodal-vtuber/blob/main/assets/images/RinAI%20Multimodal%20UX%20Example.png)

**🤖  RinAI is an open-source multi-modal desktop agent that combines speech processing, LLMs, tool automation, state machines and NEAR Intents for cross-chain trading and limit order scheduling. Features include:**

- 🎙️ Real-time STT/TTS with Groq & 11Labs
- 💸 Near Intents Integration
- 🐦 Twitter scheduling & automation
- 🧠 GraphRAG memory system
- 🔧 Extensible tool framework
- 🎮 VTube Studio integration
- 💬 YouTube chat interaction
- 🐥ElizaOS Twitter Client Integration

RinAI is built with Python, TypeScript, modern AI services, and integration with the [NEAR Intents solver bus api](https://docs.near-intents.org/near-intents).

📺 [Watch the NEAR Intents Demo](https://youtu.be/aGqrSthS2JY)

## Architecture Overview
![RinAI Architecture](https://github.com/dleerdefi/rinai-multimodal-vtuber/blob/main/assets/images/RinAI%20Multimodal%20Vtuber%20Diagram.png)

## Key Features

*   **NEAR Intents Integrations:** Integration with the NEAR Intents solver bus enables cross chain swaps on from a users near wallet
*   **Hierarchical State Machines:** State machines allow for sensitive workflows to be managed securely
*   **Approval Manager:** Approval can be implemented for tasks to provide valuable oversight to agent workflows
*   **Multimodal AI:** Integrates speech-to-text, text-to-speech, large language models, and tool calling for rich and interactive conversations.
*   **Live Streaming Ready:** Designed for V-Tubing! Operate fully autonomously, engaging directly with chat or with a live host using speech-to-text.
*   **Desktop Agent:** Operate fully autonomously, engaging directly with chat or with a live host using speech-to-text.
*   **Ultra-Fast Speech Processing:** Utilizes Groq for Whisper AI, delivering lightning-fast and reliable speech-to-text transcription.
*   **Tool-Calling Powerhouse:** Equipped with tools including:
*   **Limit Order Agent:** Use Near intents to schedule limit orders and swap across multiple chains
    *   **Twitter Agent:** Create and schedule tweets
    *   **Task Scheduling Agent:** Schedule tweet posting and other background tasks
    *   **Perplexity Integration:** Leverage Perplexity's DeepSeek R1 API for web queries
    *   **Cryptocurrency Price & Analytics:** Obtain live and historical crypto price data
 
*   **Advanced Chat Agent:**  Based on the [Rin AI Chat Agentic Chat Stack](https://github.com/dleerdefi/peak-ai-agent-stack):
    *   **RAG Memory:** Graph-based memory for context-aware responses
    *   **Keyword-Based Intent Recognition:** Fast keyword extraction for memory relevance
    *   **Advanced Context Summarization:** Active summarization for maintaining conversation context
*   **Smart LLM Gateway:** Dynamically selects optimal LLM based on task complexity
*   **Streaming Architecture:** End-to-end streaming for minimal latency
*   **Open Source & Extensible:** Built to be customizable with community contributions welcome

## NEAR Intents Workflow

**_I want to swap 5 NEAR for ETH when NEAR hits $1.20_**

* **Collect All Parameters** in a single flow (e.g., "I want to swap 5 NEAR for ETH when NEAR hits $1.20").
* **Approval Manager** ensures user reviews all swap details (e.g. chain, rate) before finalizing.
* **Scheduling & Monitoring** for:
  * **Immediate** swaps (market orders).
  * **Future** or **limit-based** swaps (price triggers).
* **Full Deposit/Execute/Withdraw** flow is **automated**—the agent orchestrates each step, so the user only sees **one** "approve" action.


The user can utilize either the speech-to-text functionality or the interface to interact with the agent and create a command; for example: **'Swap 5 NEAR for ETH on Ethereum.'**

1. **Analyze (LLM-based)**
   * Our AI agent identifies this as a Intents swap command via the **Trigger Detector** , extracting:
      1. **Source token** (e.g., NEAR)
      2. **Destination token** (e.g., ETH)
      3. **Amount** (e.g., 5)
      4. **Target price** (optional limit)
      5. **Chain** (if bridging to another blockchain)
      6. **User's wallet** (for final withdrawal)

2. **Confirm & Approve**
   * The agent organizes these details into a **Tool Operation**.
   * The **Approval Manager** presents a summary of the details: "You want to swap 5 NEAR for ETH on Ethereum if NEAR >= $1.20."
   * **Approval Manager** ensures the user is good to proceed.

3. **Scheduling Activation**
   * If it's a **limit order** or a timed operation, we spin up a **Monitoring Service** that:
      1. Polls the **Solver** for quotes every X minutes (or uses a price feed first).
      2. **If** the solver quote meets user conditions → triggers the swap **immediately**.

4. **Hierarchical State Machine** Execution
   * Sub-states handle the ephemeral nature of NEAR Intents:
      1. **Deposit** user's tokens to intents.near.
      2. **Fetch** solver quote → If user's price is met, accept & finalize the swap.
      3. **Monitor** cross-chain bridging & fill.
      4. **Withdraw** final tokens to user's wallet.
   * The user doesn't manually do each step; the agent orchestrates them under the hood.

5. **Completion**
   * Once the swap is done, our system marks the **Tool Operation** as COMPLETED.
   * The user sees a final message: "Your 5 NEAR swapped into ETH on Ethereum. Tokens withdrawn to 0xYourWallet."


**This improves the current NEAR Intents experience in the following ways:**

* **Better UX**: Hides the multiple deposit/swap/withdraw steps behind a single "approve or schedule" operation.
* **Limit Orders**: Users can automatically execute swaps **only** if the solver's price meets their target.
* **Repeating Trades**: Our scheduling logic supports **multiple tool items** (e.g. "Swap 1 NEAR daily for 5 days at $2.50+").
* **Scalable**: The same approach can be extended to **other NEAR-based actions** (NFTs, DeFi, multi-chain bridging), harnessing the same hierarchical state machine pattern.
**Tech Stack:**

## Core Components
![RinAI Architecture](https://github.com/Trove-team/rinai-multimodal-Intents-agent/blob/main/assets/images/RinAI%20State%20Machines%20Diagram.png?raw=true "State Machines Diagram")

1. **Intents Tool Script**
    *Manages the complete lifecycle of tool operations
    * Our **core** bridging logic with NEAR Intents.
    * Submits/accepts solver quotes, handles deposit/withdraw calls.

2. **Scheduling Manager**
    *Manages conditional operations like limit orders
    * The **monitoring** that checks solver quotes (or price feeds) every X minutes.
    * Triggers the **intent** execution once conditions are met.

3. **Approval Manager**
     *Handles user authorization workflow
     *States: PENDING → APPROVED/REJECTED
     *Allows asynchronous approvals (users can approve hours or days later)

4. **Agent State Manager**
    *Controls high-level conversation state (NORMAL_CHAT ↔ TOOL_OPERATION)
    *Manages the transition between conversational interactions and tool executions
    *Determines when to parse commands vs. engage in regular dialogue

5. **Orchestrator**
    *Manages the stateful workflow of tool operations
    *Routes tool operations to the respective managers/state machines

6. **AI Command Parsing**
   * Uses a large language model (LLM) or any structured approach to parse user's text into **parameters** (tokens, chain, price limit, etc.). 

7. **Advanced Features**
    *Multi-User Approval Flows: Collaborative workflows where different users handle setup vs. approval
    *Scheduled Operations: Time-based and condition-based transactions
    *Recurring Transactions: Support for "Swap 1 NEAR daily for 5 days"
    *Extensibility: Same architecture supports other NEAR-based actions (NFTs, DeFi)

*   **Backend:** Python, Node.js/TypeScript
*   **LLMs:** Role-Playing LLM, Claude 3.5
*   **Speech Processing:** Groq Whisper AI (STT), 11Labs (TTS)
*   **Frontend:** [Vtube Studio, OBS]
*   **Audio:** FFmpeg, VoiceMeeter Banana (Windows)

**Getting Started (Windows):**

1. **System Requirements:**
   * Windows 10/11
   * [VoiceMeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)
   * [VTube Studio](https://store.steampowered.com/app/1325860/VTube_Studio/)
   * [OBS Studio](https://obsproject.com/)
   * [FFmpeg](https://ffmpeg.org/download.html) (Add to PATH)

2. **Development Prerequisites:**
   * [Python 3.10+](https://www.python.org/downloads/)
   * [Node.js 18+](https://nodejs.org/)
   * [Git](https://git-scm.com/downloads)

3. **API Keys Required:**
   * Groq (Speech-to-Text)
   * 11Labs (Text-to-Speech)
   * Perplexity (Web Queries)

4. **NEAR Intents Configuration:**
*NEAR Account ID and Private Key (Private key is extremely sensitive information **BE CAREFUL HANDLING**)
*Multi-chain Account IDs (Solana, Ethereum, Bitcoin,etc)

_Be sure to add destination wallets for assets that cannot be bridged to Near wallet_

5. **Installation:**
   ```bash
   # Clone main repository
   git clone [Your Main RinAI Multimodal Intents Agent Repo URL] rinai-multimodal-Intents-agent
   cd rinai-multimodal-Intents-agent

   # Setup Python environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt

   # Setup Twitter API Client
   git clone [Your Forked ElizaOS Twitter Client Repo URL] twitter-client
   cd twitter-client
   npm install
   ```

6. **Starting the Services:**

   a. Start the Twitter API Server:
   ```bash
   cd twitter-client
   npx ts-node server.ts  # Or the correct server startup file
   ```
   - Verify the server is running at [http://localhost:3000](http://localhost:3000)

   b. Start the Main RinAI Server:
   ```bash
   cd rinai-multimodal-Intents-agent
   python src/scripts/run_stream.py
   ```
   Follow the prompts to:
   - Choose between streaming or local agent mode
   - Select your microphone device
   - Enable/disable YouTube chat (if streaming)

   c. Access the Web Interface:
   - Open your browser to [http://localhost:8765](http://localhost:8765)
   - You should see the retro-style chat interface
   - Messages will appear as they're processed

   d. Available Hotkeys:
   - `Alt+S`: Toggle speech input
   - `Alt+P`: Pause/Resume all services
   - `Alt+Q`: Quit

Each service needs to run in its own terminal window. Make sure MongoDB and Neo4j are running before starting the services.

**Open Source and Contributions:**

We welcome contributions! To get started:
1. Fork this repository
2. Create a new branch for your feature/fix
3. Submit a Pull Request

**License:**

MIT License - see [LICENSE](LICENSE) file for details
