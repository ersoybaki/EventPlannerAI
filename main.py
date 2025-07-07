from dotenv import load_dotenv
from autogen import GroupChat, GroupChatManager
import os, sys, googlemaps
from agents import create_preference_agents
sys.path.insert(0, r'C:\Users\20231455\OneDrive - TU Eindhoven\Desktop\AI Agents\EventPlannerAI')
import streamlit as st


load_dotenv()
gmaps = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

llm_config = {
    "model": "gpt-4.1-mini",  
    "api_key": os.environ.get("OPENAI_API_KEY")
}

    
def custom_speaker_selection(last_speaker, groupchat):
    messages = groupchat.messages
    
    # Debug print
    print(f"Speaker selection: Last speaker = {last_speaker.name if last_speaker else 'None'}, Total messages = {len(messages)}")
    
    # Get the current state of collected information
    state = {
        "event_type": False,
        "participants": False,
        "budget": False,
        "time": False,
        "location": False,
        "special_requests": False
    }
    
    # Go over the messages to determine what has been collected
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            if '{"event_type"' in content:
                state["event_type"] = True
            elif '{"participants"' in content:
                state["participants"] = True
            elif '{"budget_per_person"' in content:
                state["budget"] = True
            elif '{"event_time"' in content:
                state["time"] = True
            elif '{"location"' in content:
                state["location"] = True
            elif '{"special_requests"' in content:
                state["special_requests"] = True
    
    # If last speaker was proxy agent with user input, route to appropriate preference agent
    if last_speaker and last_speaker.name == "Event_Preference_Proxy_Agent":
        if not state["event_type"]:
            return groupchat.agent_by_name("Event_Type_Preference_Agent")
        elif not state["participants"]:
            return groupchat.agent_by_name("Event_Participant_Preference_Agent")
        elif not state["budget"]:
            return groupchat.agent_by_name("Event_Budget_Preference_Agent")
        elif not state["time"]:
            return groupchat.agent_by_name("Event_Time_Preference_Agent")
        elif not state["location"]:
            return groupchat.agent_by_name("Event_Location_Preference_Agent")
        elif not state["special_requests"]:
            return groupchat.agent_by_name("Event_Request_Preference_Agent")
    
    # If a preference agent just spoke, proxy should speak next
    preference_agents = [
        "Event_Type_Preference_Agent",
        "Event_Participant_Preference_Agent",
        "Event_Budget_Preference_Agent",
        "Event_Time_Preference_Agent",
        "Event_Location_Preference_Agent",
        "Event_Request_Preference_Agent"
    ]
    
    if last_speaker and last_speaker.name in preference_agents:
        last_msg = messages[-1].get("content", "") if messages else ""
        if any(pattern in last_msg for pattern in ['{"event_type"', '{"participants"', '{"budget_per_person"', '{"event_time"', '{"location"', '{"special_requests"']):
            # Check if last preference was collected and move to the next one
            if not state["participants"] and state["event_type"]:
                return groupchat.agent_by_name("Event_Participant_Preference_Agent")
            elif not state["budget"] and state["participants"]:
                return groupchat.agent_by_name("Event_Budget_Preference_Agent")
            elif not state["time"] and state["budget"]:
                return groupchat.agent_by_name("Event_Time_Preference_Agent")
            elif not state["location"] and state["time"]:
                return groupchat.agent_by_name("Event_Location_Preference_Agent")
            elif not state["special_requests"] and state["location"]:
                return groupchat.agent_by_name("Event_Request_Preference_Agent")
            elif all(state.values()):
                # All data collected, move to code generation
                return groupchat.agent_by_name("Code_Generator_Agent")
        else:
            return groupchat.agent_by_name("Event_Preference_Proxy_Agent")
    
    # code generation and execution flow
    if last_speaker:
        if last_speaker.name == "Code_Generator_Agent":
            return groupchat.agent_by_name("Code_Executor_Agent")
        elif last_speaker.name == "Code_Executor_Agent":
            return groupchat.agent_by_name("Event_Recommendation_Agent")
    
    # start with event type agent
    return groupchat.agent_by_name("Event_Type_Preference_Agent")


def extract_message_content(msg):
    if hasattr(msg, 'content'):
        content = msg.content
    elif isinstance(msg, dict) and 'content' in msg:
        content = msg['content']
    else:
        return ""
    
    # If content is a dict, extract the actual content
    if isinstance(content, dict):
        return content.get('content', str(content))
    
    return str(content)


def process_chat_messages():
    if "manager" not in st.session_state:
        return
    
    messages = st.session_state.manager.groupchat.messages
    
    # Initialize displayed_messages set 
    if "displayed_messages" not in st.session_state:
        st.session_state.displayed_messages = set()
    
    for i, msg in enumerate(messages):
        # Skip if already displayed
        if i in st.session_state.displayed_messages:
            continue
        
        # Extract message details from dict
        if isinstance(msg, dict):
            content = msg.get("content", "")
            name = msg.get("name", "assistant")
            role = msg.get("role", "assistant")
        else:
            content = extract_message_content(msg)
            name = getattr(msg, "name", "assistant")
            role = getattr(msg, "role", "assistant")
        
        # Skip empty messages
        if not content or content.strip() == "":
            st.session_state.displayed_messages.add(i)
            continue

        # Skip input echoes
        if name == "Event_Preference_Proxy_Agent" and role == "user":
            st.session_state.displayed_messages.add(i)
            continue
        
        # Skip termination messages
        if "TERMINATE" in content.upper() or (content.strip().startswith("{") and content.strip().endswith("}")):
            st.session_state.displayed_messages.add(i)
            continue
            
        # For agents that provide both a message and JSON, split them
        if name in ["Event_Type_Preference_Agent", "Event_Participant_Preference_Agent", 
                    "Event_Budget_Preference_Agent", "Event_Time_Preference_Agent",
                    "Event_Location_Preference_Agent", "Event_Request_Preference_Agent"]:
            # Look for JSON in the content
            lines = content.split('\n')
            message_to_add = None
            for line in lines:
                line = line.strip()
                if line and not line.startswith('{') and not line.upper() == "TERMINATE":
                    message_to_add = line

            if message_to_add:
                # Check if the message is already displayed
                already_displayed = any(h[1] == message_to_add for h in st.session_state.history)
                if not already_displayed:
                    st.session_state.history.append((role, message_to_add))
        else:
            already_displayed = any(h[1] == content for h in st.session_state.history)
            if not already_displayed and name != "Event_Preference_Proxy_Agent":
                st.session_state.history.append((role, content))
        
        st.session_state.displayed_messages.add(i)
# UI
st.title("Event Planner AI")
st.markdown("Let me help you plan your perfect event!")

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.history = []
    st.session_state.chat_started = False
    st.session_state.coordinator_agent = None  
    st.session_state.displayed_messages = set()  

if not st.session_state.initialized:
    # Create all agents
    type_agent, participant_agent, budget_agent, time_agent, \
    location_agent, request_agent, proxy_agent, executor_agent, \
    generator_agent, recommendation_agent, coordinator_agent = create_preference_agents()

    # Store coordinator agent reference
    st.session_state.coordinator_agent = coordinator_agent

    # Create group chat with proper configuration
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
        max_round=50,
        speaker_selection_method=custom_speaker_selection,
        allow_repeat_speaker=True
    )

    # Initialize manager    
    st.session_state.manager = GroupChatManager(
        groupchat=group_chat, 
        llm_config=llm_config,
        is_termination_msg=lambda x: False,
    )
    
    st.session_state.proxy = proxy_agent
    st.session_state.initialized = True
    
    # Add initial greeting
    st.session_state.history.append(("assistant", "Hello! Welcome to the Event Planner. What type of event would you like to plan?"))


# Display chat history
for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)


# Chat input
user_input = st.chat_input("Type your message here...")

if user_input:
    # Add user message to history and display
    st.session_state.history.append(("user", user_input))
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Process the message
    with st.spinner("Processing your request..."):
        try:
            if not st.session_state.chat_started:
                # Start the group chat
                st.session_state.chat_started = True
                
                # Initiate the chat with the manager
                st.session_state.proxy.initiate_chat(
                    st.session_state.manager,
                    message=user_input,
                    clear_history=False,
                )
            else:
                # Continue existing chat by sending to the manager
                st.session_state.proxy.send(
                    message=user_input,
                    recipient=st.session_state.manager,
                    request_reply=True
                )
            
            process_chat_messages()
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check your API keys and try again.")
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()

    st.rerun()


# Sidebar
with st.sidebar:
    st.header("Controls")
    if st.button("Reset Conversation"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    st.markdown("### Steps:")
    st.markdown("1. What type of event are you planning? ")
    st.markdown("2. How many participants will be attending? ")
    st.markdown("3. What is your budget per person? ")
    st.markdown("4. What date and time is the event? ")
    st.markdown("5. Where is the event located? ")
    st.markdown("6. Do you have any special requests or dietary requirements? ")
    st.markdown("7. I'll find the perfect venues for you!")
    