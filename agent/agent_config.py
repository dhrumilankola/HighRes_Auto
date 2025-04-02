from agents import Agent, ComputerTool, ModelSettings

def create_agent(computer):
    return Agent(
        name="JobAppAgent",
        instructions="Use tools to help fill job forms.",
        tools=[ComputerTool(computer)],
        model="computer-use-preview",
        model_settings=ModelSettings(truncation="auto"),
    )