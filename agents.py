from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
import os, sys, googlemaps

sys.path.insert(0, r'C:\Users\20231455\OneDrive - TU Eindhoven\Desktop\AI Agents\EventPlannerAI')
from helperFunctions import geocode_address, search_nearby_venues, dietary_request, get_venues_with_dietary_tags


gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

load_dotenv()
llm_config = {
    "model": "gpt-4.1-mini",
    "api_key": os.environ.get("OPENAI_API_KEY")
}

# Creating Agents for Event Planning Preferences
def create_preference_agents():
    preference_event_type_agent = ConversableAgent(
        name="Event_Type_Preference_Agent",
        system_message="""
        You are responsible for getting the event type from the user.
        Ask the user what type of event they want to plan.
        Make sure to collect the event type in a single word or a short phrase.
        If the user does not provide an event type, you can ask for more details. 
        Only speak when it's your turn to collect event type information.
        Once you have parsed the event type, respond only with a JSON object of the form {'event_type': '<event_type>'}.
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
        The integer returned should be the number of participants.
        Wait for the answer, then say "Thank you! I have the number of participants for the event."
        Only speak when it's your turn to collect the number of participants that will attend the event.
        Make sure to collect the number of participants in a single integer.
        If the user does not provide a number, you can ask for more details.
        Once you have parsed the event participants, respond only with a JSON object of the form {'participants': <number_of_participants>}.
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
        If the user only provides a value, assume it is the budget per person.
        Make sure that the total budget is equal to the budget per person multiplied with the number of participants.
        If the user provides the total budget, make sure that budget per person is equal to the total budget divided by the number of participants.
        Wait for the answer, then say "Thank you! I have the budget for the event."
        Only speak when it's your turn to collect the budget for the event.
        Make sure to collect the budget in a single integer or float value.
        If the user does not provide a budget, you can ask for more details.
        Once you have parsed the event budget, respond only with a JSON object of the form {'budget_per_person': <value>}.
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
            You are an agent that collects the date and time of the event the user wants to plan. 
            When the user provides a date and time, check if it is in the format 'DD-MM-YYYY, HH:MM'. ,
            If it is not, use the `parse_event_time` function to convert it into the correct format. 
            Wait for the answer, then say 'Thank you! I have the date and time of the event.' 
            Once you have parsed the event time, respond only with a JSON object of the form {'event_time': DD-MM-YYYY, HH:MM }.
            
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content", "").lower()
    )
    

    preference_event_location_agent = ConversableAgent(
        name="Event_Location_Preference_Agent",
        system_message="""
        You are an agent that gets the location of the event that the user wants to plan.
        The user will provide a general location, such as a city or a street, or a specific location.
        Wait for the answer, then say "Thank you! I have the location of the event."
        Only speak when it's your turn to collect event location information.
        Make sure to collect the event location in a single string that contains the address or the area of the event.
        If the user provides a location that is not specific enough, you can ask for more details.
        Once you have parsed the event location, respond only with a JSON object of the form {'location': '<event_location>'}.
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
        Wait for the answer, then say "Thank you! I have the special requests for the event."
        Only speak when it's your turn to collect special requests for the event information.
        Make sure to collect the special requests in a single string that contains the requests.
        If the user provides a request that is not clear, you can ask for more details.
        Once you have parsed the event requests, respond only with a JSON object of the form {'special_requests': '<requests>'}.
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_recommendation_agent = ConversableAgent(
        name="Event_Recommendation_Agent",
        system_message="""
        You are an agent that recommends venues for the event based on the user's preferences.
        You will receive a JSON object with the venues found according to the users's preferences.
        Put the venues in a markdown format such as:
        ```markdown
        - 1. [Venue Name]:
          Address: [Venue Address]
            Rating: [Venue Rating]
            Description: [Venue Description]
        - 2. [Venue Name]:
            Address: [Venue Address]
            Rating: [Venue Rating]
            Description: [Venue Description]
        ```
        Provide the user with 5 venues that match their preferences.
        If there are no venues that match the user's preferences, you can say "No venues found that match your preferences."
        If the user has special requests, make sure to make recommendations based on those requests.
        If the user does not have any special requests, you can recommend venues based on the event
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
        is_termination_msg = lambda x: x.get("content", "").rstrip().endswith("TERMINATE") if x.get("content") else False, 
    )


    # Creating the Local Command Line Code Executor for Venue Agent
    preference_recommendation_executor = LocalCommandLineCodeExecutor(
        timeout=120,
        work_dir="coding",
        functions=[geocode_address, search_nearby_venues, dietary_request, get_venues_with_dietary_tags],
    )

    # code executor
    codeExecutor = AssistantAgent(
        name="Code_Executor_Agent",
        code_execution_config={"work_dir": "coding", "use_docker": False},
        human_input_mode="NEVER",
    )

    # Code writer 
    codeGenerator = AssistantAgent(
        name="Code_Generator_Agent",
        system_message="""
            You are a code generator. You will receive a JSON object with the user's preferences.
            output ONLY a runnable Python code snippet, fenced as ```python```, that:

            1. import sys, json 
            2. add the system path using: sys.path.insert(0, r'C:\\Users\\20231455\\OneDrive - TU Eindhoven\\Desktop\\AI Agents\\EventPlannerAI')
            3. from helperFunctions geocode_address, search_nearby_venues, dietary_request, get_venues_with_dietary_tags
            4. loads the JSON into `prefs`  
            5. calls geocode_address(prefs['location'])     → loc  
            6. calls search_nearby_venues(lat=loc[0], lng=loc[1], radius=5000,
            keyword=prefs['type'], max_results=5) → venues  
            7. if the user has special requests, filter the venues by dietary tags using get_venues_with_dietary_tags(loc[0], loc[1], radius=5000, place_type=prefs['type'], keyword=prefs['special_requests'], max_results=5)
            8. if the user has no special requests, use the venues from step 4
            9. prints json.dumps(venues)

            Do NOT add any prose or markdown outside the ```python``` block.
            """ + preference_recommendation_executor.format_functions_for_prompt(),
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode="NEVER",
    )

    
    coordinator_agent = ConversableAgent(
        name="Coordinator_Agent",
        system_message="""
        You coordinate the event planning process.
        Keep track of what information has been collected:
        - Event type: [PENDING/COLLECTED]
        - Number of Participants: [PENDING/COLLECTED] 
        - Budget: [PENDING/COLLECTED]
        - Time: [PENDING/COLLECTED]
        - Location: [PENDING/COLLECTED]
        - Special requests: [PENDING/COLLECTED]
        
        Direct the conversation to the next agent that needs to collect information.
        When all information is collected, trigger the venue search.
        """,
    )
    
    register_function(
        geocode_address,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="geocode_address",
        description="Geocode an address to get its latitude and longitude.",
    )
    register_function(
        search_nearby_venues,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="search_nearby_venues",
        description="Search for nearby venues based on latitude, longitude, radius, keyword, and maximum results.",
    )
    register_function(
        dietary_request,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="dietary_request",
        description="Check if the venue meets the dietary requirements.",
    )
    register_function(
        get_venues_with_dietary_tags,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_venues_with_dietary_tags",
        description="Get venues with dietary tags based on location, radius, place type, keyword, and maximum results.",
    )

    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent, codeExecutor, codeGenerator, preference_event_recommendation_agent, coordinator_agent