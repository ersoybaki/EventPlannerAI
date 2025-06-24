from autogen import ConversableAgent, UserProxyAgent, AssistantAgent, initiate_chats, ChatResult
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
        You are an agent that gets the type of event that the user wants to plan.
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
        The integer returned should be the number of participants.
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
        If the user only provides a value, assume it is the budget per person.
        Make sure that the total budget is equal to the budget per person multiplied with the number of participants.
        If the user provides the total budget, make sure that budget per person is equal to the total budget divided by the number of participants.
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

                    When you have all fields, output **exactly** and then stop:

                    - **Single date+time**  
                    ```json
                    {
                        "start_date": "YYYY-MM-DD",
                        "end_date":   "YYYY-MM-DD",
                        "time":       "HH:MM",
                        "weekday":    "DayName"
                    }
                    TERMINATE

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
        is_termination_msg=lambda msg: "terminate" in msg.get("content").lower() or "TERMINATE" in msg.get("content").upper()
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
        system_message="""
        You are a code executor agent that executes code for the Event Planner.
        You execute the incoming python code and reply with its stdout only.
        """,
        llm_config=llm_config,
        code_execution_config={"executor": preference_recommendation_executor},
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
            4. calls search_nearby_venues(lat=loc[0], lng=loc[0], radius=5000,
            keyword=prefs['type'], max_results=5) → venues  
            5. prints json.dumps(venues)

            Do NOT add any prose or markdown outside the ```python``` block.
            """ + preference_recommendation_executor.format_functions_for_prompt(),
        llm_config=llm_config,
        code_execution_config=False,
        human_input_mode="NEVER",
    )
    return preference_event_type_agent, preference_event_participant_agent, \
           preference_event_budget_agent, preference_event_time_agent, \
           preference_event_location_agent, preference_event_request_agent, \
           preference_proxy_agent, codeExecutor, codeGenerator, preference_event_recommendation_agent

def preference_flow():
    type_agent, participant_agent, budget_agent, time_agent, \
    location_agent, request_agent, proxy_agent, executor_agent, generator_agent, recommendation_agent = create_preference_agents()

    steps = [
        (type_agent, "Hello, welcome to the Event Planner. What type of event would you like to plan?", "{'event_type': ''}"),
        (participant_agent, "What is the number of participants that will be attending the event?", "{'number_participants': 0}"),
        (budget_agent, "What is your budget per person for the event? If you prefer to input a total budget, please specify that.", "{'budget_per_person': 0, 'total_budget': 0}"),
        (time_agent, "What dates do you want to plan the event for? Please provide a range or a specific date, and also specify the time of day.", "{'start_date': '', 'end_date': '', 'time': '', 'weekday': ''}"),
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
    
    generate_code = [{
        "sender": proxy_agent,
        "recipient": generator_agent,
        "message": json.dumps(filled),
        "max_turns": 1,
        "clear_history": False,

    }, 
    {
        "sender": generator_agent,
        "recipient": executor_agent,
        "message": "Please generate the code to find nearby venues based on the user's preferences.",
        "max_turns": 1,
        "clear_history": False,
    },{
        "sender": executor_agent,
        "recipient": recommendation_agent,
        "message": "Here is the result from the code to find nearby venues based on the user's preferences. Give the recommendations to the user.",
        "max_turns": 1,
        "clear_history": False,
    }]
    result = initiate_chats(generate_code)[0]
    


if __name__ == "__main__":
    preference_flow()