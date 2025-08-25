from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
import os, sys, googlemaps
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

    
CODING_DIR = os.path.join(ROOT_DIR, "coding")
os.makedirs(CODING_DIR, exist_ok=True)
from helperFunctions import geocode_address, search_nearby_venues, dietary_request, get_venues_by_budget, get_venues_by_budget_and_requests, get_event_day_and_time, get_venue_opening_hours, is_open

load_dotenv()

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
        # Never display code generated or execution logs from these agents
        if self.name in ("Code_Generator_Agent", "Code_Executor_Agent"):
            return super().send(*args, **kwargs)
        # Hide any code-fenced output (```...```), regardless of agent
        content_stripped = content.strip() if content else ""
        if content_stripped.startswith("```"):
            return super().send(*args, **kwargs)
        # Otherwise show non-JSON content
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
def create_preference_agents(openai_key=None, google_key=None):
    # Use provided keys or fall back to environment variables
    api_key = openai_key or os.environ.get("OPENAI_API_KEY")
    gmaps_key = google_key or os.environ.get("GOOGLEMAPS_API_KEY")
    
    # Initialize Google Maps client with the provided key
    gmaps = googlemaps.Client(key=gmaps_key)
    
    
    llm_config = {
        "model": "gpt-4o-mini",
        "api_key": api_key
    }
    
    preference_event_type_agent = DisplayingConversableAgent(
        name="Event_Type_Preference_Agent",
           system_message="""
            You collect and normalize the event type.

            DECISION RULES (very important):
            - If the most recent message in the conversation is from the user and looks like an answer
            (i.e., not a question and not JSON), DO NOT ask anything. Parse it and output the JSON below.
            - Only ask your question if you have no usable user answer yet.
            - Never ask the same question twice.

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

            Output format (when you have enough info):
            {"event_type": "normalized_type"}
            Then say: TERMINATE

            If you truly don't have an answer yet, ask ONCE:
            "Hi! I'm here to help you plan the perfect event. What type of event are you thinking about?
            (e.g., dinner party, drinks with friends, coffee meetup, museum visit, etc.)"
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
        1. Ask the user: "Great choice! How many people will be joining you for this event?"
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
        1. Ask "Perfect! What's your budget per person in euros? (Feel free to say 'no budget' if you're flexible on price)"
        2. Wait for the user's response
        3. Extract the budget amount per person based on these rules:
        - If user provides a specific amount per person, use that amount
        - If user provides a total budget, divide it by the number of participants to get budget per person
        - If user says "no budget", "unlimited", "no limit", "doesn't matter", or similar phrases indicating no budget constraint, set budget_per_person to 1000 (this ensures all venues are considered regardless of price level)
        4. Respond with EXACTLY this format: {"budget_per_person": amount}
        5. Then say: TERMINATE
        
        Examples:
        User: "50 euros per person"
        You: {"budget_per_person": 50}
        TERMINATE
        
        User: "200 euros total" (and you know there are 4 participants)
        You: {"budget_per_person": 50}
        TERMINATE
        
        User: "No budget" or "unlimited" or "doesn't matter"
        You: {"budget_per_person": 1000}
        TERMINATE
        
        User: "I don't have a specific budget in mind"
        You: {"budget_per_person": 1000}
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
        1. Ask: "When would you like to have this event? You can tell me a specific date and time (like 'July 9th at 6:30 PM') or something general (like 'next Friday evening' or 'tomorrow morning')"
        2. Wait for the user's response.
        3. Handle the response based on these rules:
        - If user provides a specific date/time, store it verbatim without modification
        - If user says "no specific time", "anytime", "flexible", "doesn't matter", "no preference", or similar phrases indicating no time constraint, set event_time to null
        - If user says they don't know or haven't decided yet, set event_time to null
        4. Respond with EXACTLY this JSON and nothing else:
        {"event_time": "<user_input_string>"} OR {"event_time": null}
        5. Then say: TERMINATE

        Examples:
        User: "Next Friday at 8 pm"
        You: {"event_time": "Next Friday at 8 pm"}
        TERMINATE
        
        User: "Tomorrow evening"
        You: {"event_time": "Tomorrow evening"}
        TERMINATE
        
        User: "No specific time" or "anytime" or "flexible"
        You: {"event_time": null}
        TERMINATE
        
        User: "I don't know yet" or "haven't decided"
        You: {"event_time": null}
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

        IMPORTANT – conversation flow:
        1. Ask: "Where would you like to host this event? Please share a city, neighborhood, or specific area you have in mind."
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
        You collect any special requests for the event (e.g., dietary restrictions, wifi quality, quiet environment).

        IMPORTANT: Your conversation flow should be:
        1. Ask the user: "Almost done! Do you have any special requirements or preferences? (e.g., type of food if you are planning a dinner, or a quite place if you are searching for a cafe). If not, just say 'no'."
        2. Wait for the user's response.
        3. Normalize their response:
        - Convert to lowercase
        - Remove punctuation (except hyphens)
        - Trim leading/trailing whitespace
        - If multiple requests are comma-separated, keep them separated by spaces
        - Ensure it's a concise keyword or phrase suitable for a Google Places API keyword parameter
        If the input is unclear or too long, ask: "Could you please rephrase as a short keyword or phrase (e.g., 'good wifi', 'quiet environment')?"
        4. If they answer "no" or "none", treat special_requests as None.
        5. Respond with EXACTLY this JSON:
        {"special_requests": <normalized_string_or_None>}
        6. Then immediately say: TERMINATE
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
    )

    preference_event_recommendation_agent = DisplayingConversableAgent(
        name="Event_Recommendation_Agent",
        system_message="""
        You handle venue recommendations and fallback modifications.
        
        CASE 1 - Normal Recommendations:
        If you receive venue data (non-empty list), format it as:
        ```markdown
        - ### 1. [Venue Name]: 
            **Address:** [Venue Address] 
            **Rating:** [Venue Rating]/5 
            **Description:** [Venue Description] \newline
            [Google Maps Link] 
        ```
        Provide up to 5 venues and then say TERMINATE.
        
        CASE 2 - Initial Fallback Choice Handling:
        If you receive a user's fallback choice number (1, 2, 3, 4, or 5), respond as follows:
        
        Choice 1: Ask "How much larger should I search? Please specify (e.g., 'double the area', '20km radius', 'triple the search area'):" and STOP. Do NOT provide JSON yet.
        
        Choice 2: Ask "Which nearby location would you like me to search instead? Please provide a city or area name:" and STOP. Do NOT provide JSON yet.
        
        Choice 3: Ask "What's your new budget per person? Please specify the amount:" and STOP. Do NOT provide JSON yet.
        
        Choice 4: Immediately respond with: {"fallback": "remove_requests", "new_special_requests": null} and say TERMINATE.
        
        Choice 5: Ask "What type of event would you like to try instead? (e.g., bar, cafe, museum, etc.):" and STOP. Do NOT provide JSON yet.
        
        CASE 3 - Processing User's Detailed Response:
        If you receive a user's detailed response to your question (like "Amsterdam" or "double the area"), then create the appropriate JSON:
        
        For location responses: {"fallback": "change_location", "new_location": "<user_input>"}
        For radius responses: {"fallback": "expand_radius", "new_radius": <calculated_meters>}
        For budget responses: {"fallback": "increase_budget", "new_budget_per_person": <amount>}
        For event type responses: {"fallback": "change_event_type", "new_event_type": "<normalized_type>"}
        
        Then say TERMINATE.
        
        CRITICAL RULE: Never provide JSON immediately after a choice number (1-5). Always ask the question first and wait for the user's specific answer.
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
        code_execution_config={"work_dir": CODING_DIR,
                               "use_docker": False,},
        system_message="""You execute Python code and handle results.
        
        After executing code:
        1. If the output shows venues (non-empty list), proceed normally
        2. If the output is "[]" or shows no venues, respond with:
        "No venues found with the current preferences. Let me offer some alternatives."
        Then immediately suggest:
        
        "Would you like me to try one of these options?
        1. Search in a larger area
        2. Search in a different nearby location  
        3. Increase your budget range
        4. Remove special requests
        5. Try a different event type
        
        Please tell me which option you'd prefer (1-5)."
        
        Always handle Unicode/encoding errors gracefully and provide informative output.
        """,
        human_input_mode="NEVER",
    )

    # Code writer 
    codeGenerator = DisplayingAssistantAgent    (
        name="Code_Generator_Agent",
        system_message="""You generate Python code for venue searches.
            
        You will receive either:
        A) Initial user preferences JSON, OR
        B) A fallback modification JSON that modifies the original search
        
        For INITIAL SEARCH - generate standard search code using the collected preferences.
        
        For FALLBACK SEARCH - you will receive a JSON like:
        {"fallback": "expand_radius", "new_radius": 10000}
        {"fallback": "change_location", "new_location": "Amsterdam"}
        {"fallback": "increase_budget", "new_budget_per_person": 100}
        {"fallback": "remove_requests", "new_special_requests": null}
        {"fallback": "change_event_type", "new_event_type": "bar"}
        {"fallback": "change_event_time", "new_event_time": "next Friday evening"}
        
        For fallback searches, modify the original preferences accordingly and generate the same code structure.
        
        Generate this code structure:
        ```python
        import sys, json, os
        
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except: pass
        
        ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
                
        from helperFunctions import geocode_address, get_venues_by_budget_and_requests
        
        # Original preferences (use the previously collected values)
        prefs = {{
            "event_type": "restaurant",  # or whatever was collected
            "participants": 5,           # or whatever was collected
            "budget_per_person": 1000,   # or whatever was collected
            "event_time": "tomorrow evening",  # or whatever was collected
            "location": "Prague",        # or whatever was collected
            "special_requests": None     # or whatever was collected
        }}
        
        # Apply fallback modifications if provided
        # [Apply the specific modification based on fallback type - you must implement this logic]
        
        location = prefs.get('location')
        event_type = prefs.get('event_type')
        special_requests = prefs.get('special_requests')
        budget = prefs.get('budget_per_person', 1000)
        participants = prefs.get('participants', 1)
        date = prefs.get('event_time')
        radius = prefs.get('radius', 10000)  # Default to 10km for better results
        max_results = prefs.get('max_results', 5)
        
        lat, lng = geocode_address(location)
        venues = get_venues_by_budget_and_requests(
            lat=lat, lng=lng, radius=radius, place_type=event_type,
            keyword=event_type, budget_per_person=budget,
            special_request=special_requests, event_time=date, max_results=max_results
        )
        
        if venues:
            clean_venues = []
            for venue in venues:
                clean_venue = {{}}
                for key, value in venue.items():
                    if isinstance(value, str):
                        clean_value = value.encode('ascii', 'ignore').decode('ascii')
                        clean_venue[key] = clean_value
                    else:
                        clean_venue[key] = value
                clean_venues.append(clean_venue)
            output = json.dumps(clean_venues, ensure_ascii=True, indent=2)
            print(output)
        else:
            print("[]")
        ```
        
        IMPORTANT: 
        - For expand_radius: multiply the radius or set to the new_radius value
        - For change_location: replace the location with new_location
        - For increase_budget: replace budget_per_person with new_budget_per_person
        - For remove_requests: set special_requests to null
        - For change_event_type: replace event_type with new_event_type
        - For change_event_time: replace event_time with new_event_time
        
        You must implement the fallback modification logic in the code you generate. When you receive a fallback JSON, apply the changes to the prefs dictionary before using the values.
        
        Only output the ```python``` code block, nothing else.""",
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