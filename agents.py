from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
from venueAgent import VenueAgent
import os


load_dotenv()
llm_config = {
    "model": "gpt-4o",
    "api_key": os.environ.get("OPENAI_API_KEY")
}



# Creating Agents for Event Planning Preferences

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
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
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
    llm_config=False,
    code_execution_config=False,
    human_input_mode='ALWAYS',
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
)

preference_recommendation_agent = ConversableAgent(
    name="Event_Recommendation_Agent",
    system_message="""
    You are an agent that provides recommendations for the event based on the user's preferences and location.
    You will receive the user's preferences from the Event_Preference_Proxy_Agent.
    Do not ask the user for any other information and do not reply to the user.
    Return 'TERMINATE' when you have provided all the recommendations you can.
    """,
    llm_config=llm_config,
    code_execution_config=False,
    human_input_mode='NEVER', 
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
)

# --- INTEGRATING GOOGLE MAPS API FOR VENUE SEARCH ---

# Creating the Class for Venue Agent
venue_agent = VenueAgent()

# Creating the Local Command Line Code Executor for Venue Agent
venue_executor = LocalCommandLineCodeExecutor(
    timeout=60,
    work_dir="coding",
    functions=[venue_agent.geocode_address, venue_agent.search_nearby_venues]
)

# code executor
venue_executor_agent = ConversableAgent(
    name="Venue_Executor_Agent",
    llm_config=False,
    code_execution_config={"executor": venue_executor},
    human_input_mode='ALWAYS'
)

# code writer
venue_finder_agent = AssistantAgent(
    name="Venue_Finder_Agent",
    llm_config=llm_config,
    code_execution_config=False,
    human_input_mode='NEVER'
)

# Adding the functions from the venueAgent.py file to the venue_finder_agent
venue_finder_agent_system_message = venue_finder_agent.system_message
venue_finder_agent_system_message += venue_executor.format_functions_for_prompt()


# Updating the system message of the venue_finder_agent with the functions
venue_finder_agent = AssistantAgent(
    name="Venue_Finder_Agent",
    system_message=venue_finder_agent_system_message,
    llm_config=llm_config,
    code_execution_config=False,
    human_input_mode='NEVER'
)

chat_result = venue_executor_agent.initiate_chat(
    venue_finder_agent,
    message="Please find a venue for me in Eindhoven, Netherlands. I will go and get some drinks with 5 of my friends. Use the functions provided to find a suitable venue. Do not use any other functions than the ones provided in the system message of the Venue_Finder_Agent. ",
)


# --- WORKING EXAMPLE OF HOW TO USE THE AGENTS FOR PLANNING AN EVENT WITHOUT APIs ---

# Initiating the chat sequence for event planning preferences
# chats = [
#     {
#         "sender": preference_event_type_agent,
#         "recipient": preference_proxy_agent,
#         "message": "Hello, welcome to the Event Planner. What's your name and What type of event would you like to plan?",
#         "summary_method": "reflection_with_llm",

#         "summary_args": {
#             "summary_prompt" : "Return the user name and event type the user wants to plan as a JSON object only: "
#                              "{'name': '', 'type': ''}",
#         },
#         "max_turns": 1,
#         "clear_history": False, 
#     },
#     {
#         "sender": preference_event_participant_agent,
#         "recipient": preference_proxy_agent,
#         "message": "What is the number of participants that will be attending the event?",
#         "summary_method": "reflection_with_llm",

#         "summary_args": {
#             "summary_prompt" : "Return the number of participants as a JSON object only: "
#                              "{'number_participants': 0}",
#         },
#         "max_turns": 1,
#         "clear_history": False, 
#     },
#     {
#         "sender": preference_event_budget_agent,
#         "recipient": preference_proxy_agent,
#         "message": "What is your budget per person for the event? If you prefer to input a total budget, please specify that.",
#         "summary_method": "reflection_with_llm",

#         "summary_args": {
#             "summary_prompt" : "Return the budget per person and total budget as a JSON object only: "
#                              "{'budget_per_person': 0, 'total_budget': 0}",
#         },
#         "max_turns": 1,
#         "clear_history": False, 
#     },
#     {
#         "sender": preference_event_time_agent,
#         "recipient": preference_proxy_agent,
#         "message": "What dates do you want to plan the event for? Please provide a range or a specific date, and also specify the time of day.",
#         "summary_method": "reflection_with_llm",

#         "summary_args": {
#             "summary_prompt" : "Return the event dates and time as a JSON object only: "
#                              "{'start_date': '', 'end_date': '', 'time_of_day': ''}",
#         },
#         "max_turns": 1,
#         "clear_history": False, 
#     },
#     {
#         "sender": preference_event_location_agent,
#         "recipient": preference_proxy_agent,
#         "message": "What is the location of the event? You can provide a general location or a specific address.",
#         "summary_method": "reflection_with_llm",

#         "summary_args": {
#             "summary_prompt" : "Return the event location as a JSON object only: "
#                              "{'location': ''}",
#         },
#         "max_turns": 1,
#         "clear_history": False, 
#     },
#     {
#         "sender": preference_event_request_agent,
#         "recipient": preference_proxy_agent,
#         "message": "Do you have any special requests for the event? If not, you can say 'no'.",
#         "max_turns": 1,
#         "summary_method": "reflection_with_llm",
#         "summary_args": {
#             "summary_prompt" : "Return the special requests as a JSON object only: "
#                              "{'special_requests': ''}",
#         },
#         "clear_history": False,
#     },
#     {
#         "sender": preference_proxy_agent,
#         "recipient": preference_recommendation_agent,
#         "message": "Here are the user's preferences for the event. Please provide recommendations based on these preferences.",
#         "max_turns": 1,
#         "summary_method": "reflection_with_llm",
#         "clear_history": False,
#     }
# ]


# chat_results = initiate_chats(chats)