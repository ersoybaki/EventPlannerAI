from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
import os, sys, googlemaps
import streamlit as st

sys.path.insert(0, r'C:\Users\20231455\OneDrive - TU Eindhoven\Desktop\AI Agents\EventPlannerAI')
from helperFunctions import geocode_address, search_nearby_venues, dietary_request, get_venues_by_budget, get_venues_by_budget_and_dietary


gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

load_dotenv()
llm_config = {
    "model": "gpt-4.1-mini",
    "api_key": os.environ.get("OPENAI_API_KEY")
}

class TrackableAssistantAgent(AssistantAgent):
    def _process_received_message(self, message, sender, silent):
        # Extract actual message content
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = str(message)
        
        # Only display meaningful messages
        if content and not content.startswith('{"content"'):
            with st.chat_message(sender.name):
                st.markdown(content)
        
        return super()._process_received_message(message, sender, silent)

class TrackableUserProxyAgent(UserProxyAgent):
    def _process_received_message(self, message, sender, silent):
        # Extract actual message content
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = str(message)
        
        # Only display meaningful messages from user
        if content and not content.startswith('{"content"') and sender.name != "Event_Preference_Proxy_Agent":
            with st.chat_message(sender.name):
                st.markdown(content)
        
        return super()._process_received_message(message, sender, silent)


class TrackableConversableAgent(ConversableAgent):
    def _process_received_message(self, message, sender, silent):
        # Extract actual message content
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = str(message)
        
        # Only display meaningful messages
        if content and not content.startswith('{"content"'):
            # Skip JSON responses and TERMINATE messages from display
            if not (content.strip().startswith('{') and content.strip().endswith('}')) and "TERMINATE" not in content.upper():
                with st.chat_message(self.name):
                    st.markdown(content)
        
        return super()._process_received_message(message, sender, silent)
    

# Creating Agents for Event Planning Preferences
def create_preference_agents():
    preference_event_type_agent = TrackableConversableAgent(
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
        
        When you have the mapping, respond with EXACTLY this format:
        {"event_type": "normalized_type"}
        
        Then immediately say: TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER', 
    )

    preference_event_participant_agent = TrackableConversableAgent(
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
    )

    preference_event_budget_agent = TrackableConversableAgent(
        name="Event_Budget_Preference_Agent",
        system_message="""
        You collect the budget per person for the event.
        
        IMPORTANT: Your conversation flow should be:
        1. Ask "What is your budget per person for this event?"
        2. Wait for the user's response
        3. Extract the budget amount
        4. If they give total budget, divide by number of participants
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
    preference_event_time_agent = TrackableConversableAgent(
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
    )
    

    preference_event_location_agent = TrackableConversableAgent(
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
    )

    preference_event_request_agent = TrackableConversableAgent(
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
    )

    preference_event_recommendation_agent = TrackableConversableAgent(
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
    preference_proxy_agent = TrackableUserProxyAgent(
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
        functions=[geocode_address, search_nearby_venues, dietary_request, get_venues_by_budget, get_venues_by_budget_and_dietary],
    )

    # code executor
    codeExecutor = TrackableAssistantAgent(
        name="Code_Executor_Agent",
        code_execution_config={"work_dir": "coding", "use_docker": False},
        human_input_mode="NEVER",
    )

    # Code writer 
    codeGenerator = TrackableAssistantAgent(
        name="Code_Generator_Agent",
        system_message="""
            You are a code generator. You will receive a JSON object with the user's preferences.
            Output **only** a runnable Python code snippet, fenced as ```python```, that:

            1. import sys, json
            2. add the project path:
            sys.path.insert(0, r'C:\\Users\\20231455\\OneDrive - TU Eindhoven\\Desktop\\AI Agents\\EventPlannerAI')
            3. from helperFunctions import (
                geocode_address,
                search_nearby_venues,
                dietary_request,
                get_venues_by_budget,
                get_venues_by_budget_and_dietary
            )

            4. Load the JSON payload into `prefs`, e.g.:
            prefs = json.loads(input_json_string)

            5. Pull out all possible settings with safe defaults:
            location         = prefs.get('location')
            event_type       = prefs.get('event_type')
            special_requests = prefs.get('special_requests')
            budget           = prefs.get('budget')
            radius           = prefs.get('radius', 5000)
            max_results      = prefs.get('max_results', 5)

            6. Always geocode first:
            lat, lng = geocode_address(location)

            7. Decide which helper to call based on presence of `budget` and `special_requests`:
            - If both `budget` and `special_requests` are provided:
                venues = get_venues_by_budget_and_dietary(
                    lat=lat, lng=lng,
                    radius=radius,
                    place_type=event_type,
                    keyword=event_type,
                    budget_per_person=budget,
                    dietary_keyword=special_requests,
                    max_results=max_results
                )
            - Elif only `budget` is provided:
                venues = get_venues_by_budget(
                    lat=lat, lng=lng,
                    radius=radius,
                    place_type=event_type,
                    keyword=event_type,
                    budget_per_person=budget,
                    max_results=max_results
                )

            8. Print the results as JSON:
            print(json.dumps(venues, ensure_ascii=False))

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
        get_venues_by_budget_and_dietary,
        caller=codeGenerator,
        executor=preference_proxy_agent,
        name="get_venues_by_budget_and_dietary",
        description="Get venues by budget and dietary requirements based on latitude, longitude, radius, place type, keyword, budget per person, dietary keyword, and maximum results.",
    )

    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent, codeExecutor, codeGenerator, preference_event_recommendation_agent, coordinator_agent