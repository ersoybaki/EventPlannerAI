
from dotenv import load_dotenv
from autogen import GroupChat, GroupChatManager
import os, sys, googlemaps
from agents import create_preference_agents
sys.path.insert(0, r'C:\Users\20231455\OneDrive - TU Eindhoven\Desktop\AI Agents\EventPlannerAI')
from helperFunctions import geocode_address, search_nearby_venues, dietary_request, get_venues_with_dietary_tags


gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

load_dotenv()
llm_config = {
    "model": "gpt-4.1-mini",
    "api_key": os.environ.get("OPENAI_API_KEY")
}

    
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
                       ['recommendation', 'suggest', 'option', 'event', 'venue', 'address', 'rating']):
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