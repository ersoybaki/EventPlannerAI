from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
import os, sys, googlemaps
import streamlit as st

sys.path.insert(0, r'C:\Users\20231455\OneDrive - TU Eindhoven\Desktop\AI Agents\EventPlannerAI')
from helperFunctions import geocode_address, search_nearby_venues, dietary_request, get_venues_by_budget, get_venues_by_budget_and_requests, get_event_day_and_time, get_venue_opening_hours, is_open


gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

load_dotenv()
llm_config = {
    "model": "gpt-4.1-mini",
    "api_key": os.environ.get("OPENAI_API_KEY")
}

if "shown" not in st.session_state:
    st.session_state.shown = set()  

def safe_markdown(sender_name: str, content: str) -> None:
    key = (sender_name, content.strip())

    # if duplicate message, do not show it again
    if key in st.session_state.shown:
        return  

    st.session_state.shown.add(key)
    with st.chat_message(sender_name[0]):
        st.markdown(content)


class DisplayingAssistantAgent(AssistantAgent):
    def send(self, *args, **kwargs):
        msg = args[0] if args else kwargs.get("message")
        content = (
            msg.get("content") if isinstance(msg, dict)
            else str(msg)
        )
        if content and not content.startswith("{"):
            safe_markdown(self.name, content)
        return super().send(*args, **kwargs)


class DisplayingConversableAgent(ConversableAgent):
    def send(self, *args, **kwargs):
        msg = args[0] if args else kwargs.get("message")
        content = (
            msg.get("content") if isinstance(msg, dict)
            else str(msg)
        )
        if content and not content.startswith("{"):
            safe_markdown(self.name, content)
        return super().send(*args, **kwargs)


class DisplayingUserProxyAgent(UserProxyAgent):
    def send(self, *args, **kwargs):
        msg = args[0] if args else kwargs.get("message")
        content = (
            msg if isinstance(msg, str)
            else msg.get("content", "")
        )
        if content:
            safe_markdown("user", content)
        return super().send(*args, **kwargs)
    
    
# Creating Agents for Event Planning Preferences
def create_preference_agents():
    preference_event_type_agent = DisplayingConversableAgent(
        name="Event_Type_Preference_Agent",
        system_message="""
        You are responsible for getting the event type from the user and normalizing it.
        
        IMPORTANT: Your conversation flow should be:
        1. Ask the user what type of event they want to plan
        2. Take their answer and map it to a Google Places API type
        3. Respond ONLY with the JSON format specified below
        4. Then say TERMINATE
        
        Mapping rules:
        - dinner, lunch, brunch, meal, food, banquet, dinner party → restaurant
        - drinks, cocktails, happy hour, night out → bar  
        - coffee, café, tea, coffee shop → cafe
        - picnic, outdoors, park, green space → park
        - museum, gallery, art exhibition → museum
        - hotel, lodging, overnight, stay → hotel
        - cinema, movie, film screening → movie_theater
        - gym, fitness, workout, exercise → gym
        - bookstore, library, books → book_store
        - sports, stadium, arena, match → stadium

        DO NOT repeat the question multiple times. Ask once and wait for response.
        
        When you have the mapping, respond with EXACTLY this format:
        {"event_type": "normalized_type"}
        
        Then immediately say: TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER', 
    )

    preference_event_participant_agent = DisplayingConversableAgent(
        name="Event_Participant_Preference_Agent",
        system_message="""
        You collect the number of participants for the event.

        IMPORTANT: Your conversation flow should be:
        1. Ask the user: "How many participants will be attending this event?"
        2. Wait for the user's response.
        3. Extract the integer count of participants from their reply.
        4. If no integer is found, ask for clarification: 
        "I didn't catch the number of participants. Could you please specify it as a single integer?"
        5. Once you have the integer, respond with EXACTLY this format: {"participants": <number>}
        6. Then say: TERMINATE

        DO NOT repeat the question multiple times. Ask once and wait for response.

        Example:
        User: "There will be 8 people attending"
        You: {"participants": 8}
        TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )

    preference_event_budget_agent = DisplayingConversableAgent(
        name="Event_Budget_Preference_Agent",
        system_message="""
        You collect the budget per person for the event.
        
        IMPORTANT: Your conversation flow should be:
        1. Ask "What is your budget per person for this event?"
        2. Wait for the user's response
        3. Extract the budget amount per person
        4. If user specifically provides a total budget, divide it by the number of participants to get the budget per person.
        5. Respond with EXACTLY this format: {"budget_per_person": amount}
        6. Then say: TERMINATE
        
        Example:
        User: "50 euros per person"
        You: {"budget_per_person": 50}
        TERMINATE
        
        User: "200 euros total" (and you know there are 4 participants)
        You: {"budget_per_person": 50}
        TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )
    preference_event_time_agent = DisplayingConversableAgent(
        name="Event_Time_Preference_Agent",
        system_message="""           
        You collect the date and time string for the event exactly as the user provides it.

        IMPORTANT: Your conversation flow should be:
        1. Ask: "When is the event scheduled? Please provide date and time (e.g., '09-07-2025 18:30', 'tomorrow evening' or 'next week Wednesday 6 PM)."
        2. Wait for the user's response.
        3. Take the user’s response verbatim and store it without modification.
        4. Respond with EXACTLY this JSON and nothing else:
        {"event_time": "<user_input_string>"}
        5. Then say: TERMINATE

        Example:
        User: "Next Friday at 8 pm"
        You: {"event_time": "Next Friday at 8 pm"}
        TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )
    

    preference_event_location_agent = DisplayingConversableAgent(
        name="Event_Location_Preference_Agent",
        system_message="""
        You collect the event location exactly as the user says it.

        IMPORTANT — conversation flow:
        1. Ask: "Where will the event take place? Please provide a city or an area."
        2. Wait for the user's reply.
        3. Store the reply verbatim.
        4. If the location is too vague, ask for clarification:
        "Could you provide a more specific location?"
        5. Once you have the location string, respond with EXACTLY this format:
        {"location": "<user_input_string>"}
        6. Then immediately say: TERMINATE

        Example:
        User: "Central Park, New York"
        You: {"location": "Central Park, New York"}
        TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )

    preference_event_request_agent = DisplayingConversableAgent(
        name="Event_Request_Preference_Agent",
        system_message="""
        You collect any special requests for the event (e.g., dietary restrictions, wifi quality, quiet environment, seating preferences).

        IMPORTANT: Your conversation flow should be:
        1. Ask the user: "Do you have any special requests for this event?"
        2. Wait for the user's response.
        3. Normalize their response:
        - Convert to lowercase
        - Remove punctuation (except hyphens)
        - Trim leading/trailing whitespace
        - If multiple requests are comma-separated, keep them separated by spaces
        - Ensure it’s a concise keyword or phrase suitable for a Google Places API keyword parameter
        If the input is unclear or too long, ask: "Could you please rephrase as a short keyword or phrase (e.g., 'good wifi', 'quiet environment')?"
        4. If they answer "no" or "none", treat special_requests as None.
        5. Respond with EXACTLY this JSON:
        {"special_requests": <normalized_string_or_null>}
        6. Then immediately say: TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )

    preference_event_recommendation_agent = DisplayingConversableAgent(
        name="Event_Recommendation_Agent",
        system_message="""
        You are an agent that recommends venues for the event based on the user's preferences.
        You will receive a JSON object with the venues found according to the users's preferences.
        Put the venues in a markdown format such as:
        ```markdown
        - 1. [Venue Name]:
          Address: [Venue Address]
            Rating: [Venue Rating]/5
            Description: [Venue Description]
        - 2. [Venue Name]:
            Address: [Venue Address]
            Rating: [Venue Rating]/5
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
    )
    preference_proxy_agent = DisplayingUserProxyAgent(
        name="Event_Preference_Proxy_Agent",
        llm_config=False,
        code_execution_config=False,
        human_input_mode='ALWAYS',
        is_termination_msg=lambda msg: "terminate" in msg.get("content", "").lower()
    )


    # Creating the Local Command Line Code Executor for Venue Agent
    preference_recommendation_executor = LocalCommandLineCodeExecutor(
        timeout=120,
        work_dir="coding",
        functions=[geocode_address, search_nearby_venues, dietary_request, get_venues_by_budget, get_venues_by_budget_and_requests, get_event_day_and_time, get_venue_opening_hours, is_open],
    )

    # code executor
    codeExecutor = DisplayingAssistantAgent (
        name="Code_Executor_Agent",
        code_execution_config={"work_dir": "coding",
                               "use_docker": False,},
        human_input_mode="NEVER",
    )

    # Code writer 
    codeGenerator = DisplayingAssistantAgent    (
        name="Code_Generator_Agent",
        system_message="""You are a code generator. You will receive a JSON object with the user's preferences.
            Output **only** a runnable Python code snippet, fenced as ```python```, that:

            1. import sys, json
            2. add the project path:
            sys.path.insert(0, r'C:\\Users\\20231455\\OneDrive - TU Eindhoven\\Desktop\\AI Agents\\EventPlannerAI')
            3. from helperFunctions import (
                geocode_address,
                search_nearby_venues,
                get_venues_by_budget,
                get_venues_by_budget_and_requests,
                get_event_day_and_time,
                get_venue_opening_hours,
                is_open
            )

            4. Load the JSON payload into `prefs`, e.g.:
            prefs = json.loads(input_json_string)

            5. Pull out all possible settings with safe defaults:
            location         = prefs.get('location')
            event_type       = prefs.get('event_type')
            special_requests = prefs.get('special_requests')
            budget           = prefs.get('budget')
            participants     = prefs.get('participants', 1)
            date             = prefs.get('event_date')
            radius           = prefs.get('radius', 5000)
            max_results      = prefs.get('max_results', 5)

            6. Always geocode first:
            lat, lng = geocode_address(location)

            7. Decide which helper to call based on `budget` and `special_requests`:
            venues = get_venues_by_budget_and_requests(
                lat=lat, lng=lng,
                radius=radius,
                place_type=event_type,
                keyword=event_type,
                budget_per_person=budget,
                special_request=special_requests,
                event_time=date,
                max_results=max_results
            )

            8. Print the results as JSON:
            output = json.dumps(venues, ensure_ascii=False)
            sys.stdout.buffer.write(output.encode("utf-8"))

            Do NOT add any prose or markdown outside the ```python``` block.
            """,
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
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: "terminate" in msg.get("content", "").lower(),
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
        get_venues_by_budget,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_venues_by_budget",
        description="Get venues by budget based on latitude, longitude, radius, place type, keyword, budget per person, and maximum results.",
    )
    register_function(
        get_venues_by_budget_and_requests,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_venues_by_budget_and_requests",
        description="Get venues by budget and dietary requirements based on latitude, longitude, radius, place type, keyword, budget per person, dietary keyword, and maximum results.",
    )
    register_function(
        get_event_day_and_time,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_event_day_and_time",
        description="Get the event day and time based on the provided answer.",
    )
    register_function(
        get_venue_opening_hours,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_venue_opening_hours",
        description="Get the opening hours of a venue based on its latitude and longitude.",
    )
    register_function(
        is_open,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="is_open",
        description="Check if a venue is open based on its latitude, longitude, and event time.",
    )

    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent, codeExecutor, codeGenerator, preference_event_recommendation_agent, coordinator_agent