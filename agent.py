import sys
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# 1. Initialize the Tool
tavily_search_tool = TavilySearch(max_results=10)

# 2. Setup Memory (Checkpointer) for multi-round conversations
memory = MemorySaver()

# 3. Create the Agent using your exact function
agent = create_agent(
    model="openai:gpt-5.4",
    tools=[tavily_search_tool],
    system_prompt="""Tu es un avocat spécialiste du droit français. 
Ton rôle est de répondre à des questions juridiques en faisant des recherches approfondies dans la loi en vigueur et la jurisprudence.
Tes réponses doivent être sourcées et tenir compte des dernières évolutions juridiques.
Explique ton raisonnement et fournis une réponse claire et non ambigüe. 
""",
    checkpointer=memory  # This is the single argument needed to turn on memory!
)

# 4. Define the thread ID for this specific conversation
config = {"configurable": {"thread_id": "dossier_interactif_1"}}

print("=== Assistant Juridique IA ===")
print("Posez vos questions. Tapez 'quit', 'exit' ou 'q' pour quitter.\n")

# 5. The Interactive Loop
while True:
    try:
        user_input = input("\nVous : ")
    except (KeyboardInterrupt, EOFError):
        # Handles CTRL+C gracefully
        print("\nAu revoir !")
        sys.exit()

    # Exit condition
    if user_input.lower() in ["quit", "exit", "q"]:
        print("Au revoir !")
        break

    # Send the input to the agent and stream the response
    for step in agent.stream(
        {"messages": [("user", user_input)]},
        config=config,
        stream_mode="values"
    ):
        latest_message = step["messages"][-1]

        # Filter out the "human" message so the terminal doesn't just echo your prompt back
        if latest_message.type != "human":
            latest_message.pretty_print()
