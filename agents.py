from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from dotenv import load_dotenv
from venueAgent import geocode_address, search_nearby_venues
import os, json, re, ast, googlemaps
import datetime

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
        Wait for the answer, then say "Thank you! I have the event type."
        Only speak when it's your turn to collect event type information.
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
        Return 'TERMINATE' when you have gathered all the information you need.
        """,
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode='NEVER',
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower()
    )

    preference_event_time_agent = ConversableAgent(
        name="Event_Time_Preference_Agent",
        system_message= " You are an agent that gets the date and time of the event that the user wants to plan. Remember that todays date is " + str(datetime.datetime.now().isoformat()) +
        """
            When the user provides a date and time, you will parse it and return it in a specific format.
            When relative terms are used (like "today", "tomorrow", etc.), you will resolve them based on the system's current date.
            You will return the date in the format "YYYY-MM-DD" and the time in the format "HH:MM" and also the day of the week as a string.
            If the user provides a date range, you will return the start and end dates in the same format.
            If the user provides a single date, you will return the same date for both start and end dates, along with the time and day of the week.
            Normalize fuzzy times into 24-hour format and populate the `"time"` field for single dates:
                - “morning” → “09:00”
                - “noon” → “12:00”
                - “afternoon” → “16:00”
                - “evening” → “18:00”
                - “night” → “20:00”
                - “midnight” → “00:00”
            Wait for the answer, then say "Thank you! I have the event time."
            Only speak when it's your turn to collect event time information.
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
        Wait for the answer, then say "Thank you! I have the location of the event."
        Only speak when it's your turn to collect event location information.
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
        - 1. Venue Name: [Venue Name]
          Address: [Venue Address]
            Rating: [Venue Rating]
            Description: [Venue Description]
        - 2. Venue Name: [Venue Name]
            Address: [Venue Address]
            Rating: [Venue Rating]
            Description: [Venue Description]
        ```
        Provide the user with 5 venues that match their preferences.
        If there are no venues that match the user's preferences, you can say "No venues found that match your preferences."
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
        functions=[geocode_address, search_nearby_venues],
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
            You are a code generator. When I give you a JSON of event preferences,
            output ONLY a runnable Python code snippet, fenced as ```python```, that:

            1. imports json, geocode_address, search_nearby_venues  
            2. loads the JSON into `prefs`  
            3. calls geocode_address(prefs['location']) → loc  
            4. calls search_nearby_venues(lat=loc[0], lng=loc[1], radius=5000,
            keyword=prefs['type'], max_results=5) → venues  
            5. prints json.dumps(venues)

            Do NOT add any prose or markdown outside the ```python``` block.
            """ + preference_recommendation_executor.format_functions_for_prompt(),
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode="NEVER",
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

    coordinator_agent = ConversableAgent(
        name="Coordinator_Agent",
        system_message="""
        You coordinate the event planning process.
        Keep track of what information has been collected:
        - Event type: [PENDING/COLLECTED]
        - Participants: [PENDING/COLLECTED] 
        - Budget: [PENDING/COLLECTED]
        - Time: [PENDING/COLLECTED]
        - Location: [PENDING/COLLECTED]
        - Special requests: [PENDING/COLLECTED]
        
        Direct the conversation to the next agent that needs to collect information.
        When all information is collected, trigger the venue search.
        """,
    )

    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent, codeExecutor, codeGenerator, preference_event_recommendation_agent, coordinator_agent
    
def custom_speaker_selection(last_speaker, groupchat):
    
    # Define the conversation flow order
    flow_order = [
        # Start and coordinate
        "Coordinator_Agent",       
           
        "Event_Type_Preference_Agent",       
        "Event_Preference_Proxy_Agent",  

        "Event_Participant_Preference_Agent",   
        "Event_Preference_Proxy_Agent",

        "Event_Budget_Preference_Agent",        
        "Event_Preference_Proxy_Agent",  

        "Event_Time_Preference_Agent",         
        "Event_Preference_Proxy_Agent",    

        "Event_Location_Preference_Agent",      
        "Event_Preference_Proxy_Agent",   

        "Event_Request_Preference_Agent",       
        "Event_Preference_Proxy_Agent",  

        "Coordinator_Agent",                    
        "Code_Generator_Agent",                
        "Code_Executor_Agent",                 
        "Event_Recommendation_Agent",           
    ]
    
    messages = groupchat.messages
    last_speaker_name = last_speaker.name if last_speaker else ""

    # Check if we've reached the recommendation phase and if recommendations have been provided
    def has_recommendations_been_provided():
        # Check recent messages first
        for msg in reversed(messages):  
            if (hasattr(msg, 'name') and msg.name == "Event_Recommendation_Agent" and  msg.content and len(msg.content.strip()) > 50):
                if any(keyword in msg.content.lower() for keyword in 
                       ['recommendation', 'suggest', 'option', 'event', 'venue']):
                    return True
        return False
    
    # If we're past the basic flow and recommendations have been provided, allow for follow-up questions or end the conversation
    if len(messages) >= len(flow_order) and has_recommendations_been_provided():

        # Check if the last message was from user asking follow-up questions
        if (last_speaker_name == "Event_Preference_Proxy_Agent" and 
            messages and messages[-1].content):
            return groupchat.agent_by_name("Coordinator_Agent")
        else:
            return groupchat.agent_by_name("Coordinator_Agent")
        

    # Follow the original flow structure
    if len(messages) < len(flow_order):
        try:
            next_agent_name = flow_order[len(messages)]
            return groupchat.agent_by_name(next_agent_name)
        except:
            pass
    
    # If we've gone through the flow but recommendations haven't been provided yet, ensure we get to the recommendation agent
    if not has_recommendations_been_provided():
        return groupchat.agent_by_name("Event_Recommendation_Agent")
    
    # Default fallback
    return groupchat.agents[0]

def group_chat_recommendations():
    type_agent, participant_agent, budget_agent, time_agent, \
    location_agent, request_agent, proxy_agent, executor_agent, generator_agent, recommendation_agent, coordinator_agent = create_preference_agents()

    group_chat = GroupChat(
         agents=[
            coordinator_agent,      
            type_agent,            
            participant_agent,    
            budget_agent,          
            time_agent,           
            location_agent,      
            request_agent,        
            generator_agent,      
            executor_agent,       
            recommendation_agent, 
            proxy_agent          
        ],
        messages=[],
        speaker_selection_method=custom_speaker_selection,
        max_round=30,
    )

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )

    results = proxy_agent.initiate_chat(group_chat_manager,
        messages="Hello, welcome to the Event Planner. What type of event would you like to plan?", 
        max_turns=35, 
        clear_history=True,)

    return results
if __name__ == "__main__":
    group_chat_recommendations()