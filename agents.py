from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
from venueAgent import geocode_address, search_nearby_venues
import os, json, re, ast, googlemaps

gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

load_dotenv()
llm_config = {
    "model": "gpt-4o",
    "api_key": os.environ.get("OPENAI_API_KEY")
}



# Creating Agents for Event Planning Preferences
def create_preference_agents():
    preference_event_type_agent = ConversableAgent(
        name="Event_Type_Preference_Agent",
        system_message="""
        You are an agent that gets the user's name and the type of event that the user wants to plan.
        Do not ask the user for any other information and do not reply to the user.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER', 
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower(),
    )

    preference_event_participant_agent = ConversableAgent(
        name="Event_Participant_Preference_Agent",
        system_message="""
        You are an agent that gets the number of participants of the event that the user wants to plan.
        Adress the user by their name and ask how many participants will be attending the event.
        Do not ask the user for any other information and do not reply to the user.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_budget_agent = ConversableAgent(
        name="Event_Budget_Preference_Agent",
        system_message="""
        You are an agent that gets the budget per person for the participants of the event.
        Address the user by their name and ask ask if the user prefers to input a total budget, if so, ask for the total budget.
        Do not ask the user for any other information and do not reply to the user.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_time_agent = ConversableAgent(
        name="Event_Time_Preference_Agent",
        system_message="""
        You are an agent that gets the dates the user wants to plan. The dates can be a range or a specific date.
        Address the user by their name and ask for the dates.
        If the user provides a range, ask for the start and end dates.
        If the user provides a specific date, ask for the date.
        Also, ask for the time of the day for the event.
        Do not ask the user for any other information and do not reply to the user.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_location_agent = ConversableAgent(
        name="Event_Location_Preference_Agent",
        system_message="""
        You are an agent that gets the location of the event that the user wants to plan.
        The user will provide a general location, such as a city or a street, or a specific location.
        Do not ask the user for any other information.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_request_agent = ConversableAgent(
        name="Event_Request_Preference_Agent",
        system_message="""
        You are an agent that gets the user's special requests for the event they want to plan if they have any.
        The user will provide a request, such as "vegan food" or "wheelchair accessibility".
        If the user does not have any special requests, you can return 'TERMINATE'.
        Do not ask the user for any other information.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_proxy_agent = UserProxyAgent(
        name="Event_Preference_Proxy_Agent",
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='ALWAYS',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower() or "TERMINATE" in msg.get("content").upper()
    )


    # Creating the Local Command Line Code Executor for Venue Agent
    preference_recommendation_executor = LocalCommandLineCodeExecutor(
        timeout=120,
        work_dir="coding",
        functions=[geocode_address, search_nearby_venues],
    )

    # Code writer and executor
    preference_recommendation_agent = AssistantAgent(
        name="Preference_Recommendation_Agent",
        system_message="""
        You are a helpful event-planning assistant. You have two tools:
        1) geocode_address(address: str) → returns lat/lng JSON
        2) search_nearby_venues(lat: float, lng: float,
                            radius: int, keyword: str,
                            max_results: int) → returns list of venues
        
        When the user provides their preferences JSON, you should:
        - Extract the location, event type, budget, participants, date/time, special requests
        - Call geocode_address() on the user’s “location”
        - Call search_nearby_venues() with appropriate parameters (e.g. radius 5000m,
        keyword = event type, max_results = 5)
        - Format the returned venues into a markdown list, including name, address,
        and any other useful info.
        
        Do not call external APIs directly—use only the provided functions.
        """,
        llm_config=llm_config,
        code_execution_config={"executor": preference_recommendation_executor},
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: "terminate" in msg.get("content", "").lower(),
    )

    # Adding the functions from the venueAgent.py file to the preference_recommendation_agent
    preference_recommendation_agent_system_message = preference_recommendation_agent.system_message
    preference_recommendation_agent_system_message += preference_recommendation_executor.format_functions_for_prompt()
    

    # Updating the system message of the preference_recommendation_agent with the functions
    preference_recommendation_agent = AssistantAgent(
        name="Preference_Recommendation_Agent",
        system_message=preference_recommendation_agent_system_message,
        llm_config=llm_config,
        code_execution_config={"executor": preference_recommendation_executor},
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: "terminate" in msg.get("content", "").lower(),
    )

    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent,  preference_recommendation_agent

def preference_flow():
    type_agent, participant_agent, budget_agent, time_agent, \
    location_agent, request_agent, proxy_agent, recommendation_agent = create_preference_agents()

    steps = [
        (type_agent, "Hello, welcome to the Event Planner. What's your name and What type of event would you like to plan?", "{'name': '', 'type': ''}"),
        (participant_agent, "What is the number of participants that will be attending the event?", "{'number_participants': 0}"),
        (budget_agent, "What is your budget per person for the event? If you prefer to input a total budget, please specify that.", "{'budget_per_person': 0, 'total_budget': 0}"),
        (time_agent, "What dates do you want to plan the event for? Please provide a range or a specific date, and also specify the time of day.", "{'start_date': '', 'end_date': '', 'time_of_day': ''}"),
        (location_agent, "What is the location of the event? You can provide a general location or a specific address.", "{'location': ''}"),
        (request_agent, "Do you have any special requests for the event? If not, you can say 'no'.", "{'special_requests': ''}"),
    ]

    filled = {}

    for agent, question, json_schema in steps:
        chat = [{
            "sender": agent,
            "recipient": proxy_agent,
            "message": question,
            "summary_method": "reflection_with_llm",
            "summary_args": {
                "summary_prompt": f"Return the user preference as a JSON object only: {json_schema}",
            },
            "max_turns": 1,
            "clear_history": False,
        }]

        result = initiate_chats(chat)
        chat_res: ChatResult = result[0]
        raw = chat_res.summary

        # if there’s any stray fences, remove them
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

        slot: dict = ast.literal_eval(clean)
        filled.update(slot)
    
    preference_input = json.dumps(filled)
    final_chat = [{
        "sender": proxy_agent,
        "recipient": recommendation_agent,
        "message": preference_input,
        "max_turns": 10,
        "clear_history": False,
    },

    ]
    res = initiate_chats(final_chat)[0]
    print(res.summary) 


if __name__ == "__main__":
    preference_flow()