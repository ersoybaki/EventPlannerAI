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
    
    # Debug print current state
    print(f"Current state: {state}")
    
    selected_agent = None
    
    # If last speaker was proxy agent with user input, route to appropriate preference agent
    if last_speaker and last_speaker.name == "Event_Preference_Proxy_Agent":
        if not state["event_type"]:
            selected_agent = groupchat.agent_by_name("Event_Type_Preference_Agent")
        elif not state["participants"]:
            selected_agent = groupchat.agent_by_name("Event_Participant_Preference_Agent")
        elif not state["budget"]:
            selected_agent = groupchat.agent_by_name("Event_Budget_Preference_Agent")
        elif not state["time"]:
            selected_agent = groupchat.agent_by_name("Event_Time_Preference_Agent")
        elif not state["location"]:
            selected_agent = groupchat.agent_by_name("Event_Location_Preference_Agent")
        elif not state["special_requests"]:
            selected_agent = groupchat.agent_by_name("Event_Request_Preference_Agent")
        elif all(state.values()):
            selected_agent = groupchat.agent_by_name("Code_Generator_Agent")
    
    # If a preference agent just spoke, determine next step
    elif last_speaker:
        preference_agents = [
            "Event_Type_Preference_Agent",
            "Event_Participant_Preference_Agent",
            "Event_Budget_Preference_Agent",
            "Event_Time_Preference_Agent",
            "Event_Location_Preference_Agent",
            "Event_Request_Preference_Agent"
        ]
        
        if last_speaker.name in preference_agents:
            last_msg = messages[-1].get("content", "") if messages else ""
            
            # Check if the agent just provided a JSON response
            if any(pattern in last_msg for pattern in ['{"event_type"', '{"participants"', '{"budget_per_person"', '{"event_time"', '{"location"', '{"special_requests"']):
                # Agent has collected data, move to next agent
                if state["event_type"] and not state["participants"]:
                    selected_agent = groupchat.agent_by_name("Event_Participant_Preference_Agent")
                elif state["participants"] and not state["budget"]:
                    selected_agent = groupchat.agent_by_name("Event_Budget_Preference_Agent")
                elif state["budget"] and not state["time"]:
                    selected_agent = groupchat.agent_by_name("Event_Time_Preference_Agent")
                elif state["time"] and not state["location"]:
                    selected_agent = groupchat.agent_by_name("Event_Location_Preference_Agent")
                elif state["location"] and not state["special_requests"]:
                    selected_agent = groupchat.agent_by_name("Event_Request_Preference_Agent")
                elif all(state.values()):
                    # All data collected, move to code generation
                    selected_agent = groupchat.agent_by_name("Code_Generator_Agent")
            else:
                # Agent is asking a question, go to proxy for user input
                selected_agent = groupchat.agent_by_name("Event_Preference_Proxy_Agent")
        
        # Handle code generation and execution flow
        elif last_speaker.name == "Code_Generator_Agent":
            selected_agent = groupchat.agent_by_name("Code_Executor_Agent")
        elif last_speaker.name == "Code_Executor_Agent":
            selected_agent = groupchat.agent_by_name("Event_Recommendation_Agent")
        elif last_speaker.name == "Event_Recommendation_Agent":
            # End of flow
            selected_agent = None
    
    # If no agent selected yet, start with event type agent
    if selected_agent is None and len(messages) == 0:
        selected_agent = groupchat.agent_by_name("Event_Type_Preference_Agent")
    
    # Debug print selected agent
    if selected_agent:
        print(f"Selected next speaker: {selected_agent.name}")
    else:
        print("No agent selected (conversation may be complete)")
    
    return selected_agent

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
    
    # Initialize tracking sets
    if "processed_indices" not in st.session_state:
        st.session_state.processed_indices = set()
    if "displayed_questions" not in st.session_state:
        st.session_state.displayed_questions = set()
    
    # Debug print
    print(f"Processing {len(messages)} messages, already processed: {len(st.session_state.processed_indices)}")
    
    new_messages_found = False
    
    for i, msg in enumerate(messages):
        # Skip if already processed
        if i in st.session_state.processed_indices:
            continue
        
        # Mark as processed immediately
        st.session_state.processed_indices.add(i)
        
        # Extract message details
        if isinstance(msg, dict):
            content = msg.get("content", "")
            name = msg.get("name", "assistant")
            role = msg.get("role", "assistant")
        else:
            continue
        
        # Debug print
        print(f"Processing message {i} from {name} (role: {role}): {content[:50]}...")
        
        # Skip empty messages
        if not content or content.strip() == "":
            continue
        
        # Skip coordinator agent messages
        if name == "Coordinator_Agent":
            continue
            
        # Skip proxy agent messages (both user and assistant roles)
        if name == "Event_Preference_Proxy_Agent":
            continue
        
        # Handle preference agent messages
        if name in ["Event_Type_Preference_Agent", "Event_Participant_Preference_Agent", 
                    "Event_Budget_Preference_Agent", "Event_Time_Preference_Agent",
                    "Event_Location_Preference_Agent", "Event_Request_Preference_Agent"]:
            
            # Split content into lines
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                # Skip empty lines, JSON, and TERMINATE
                if not line or line.startswith('{') or "TERMINATE" in line.upper():
                    continue
                
                # This is a question/statement from the agent
                if line not in st.session_state.displayed_questions:
                    st.session_state.displayed_questions.add(line)
                    # Check if it's already in history
                    if line not in [h[1] for h in st.session_state.history]:
                        st.session_state.history.append(("assistant", line))
                        print(f"Added to history: {line}")
                        new_messages_found = True
                break
            
        elif name in ["Code_Generator_Agent", "Code_Executor_Agent"]:
            # for these two, we still skip JSON but also skip fenced code:
            if not (content.strip().startswith('{') or content.strip().startswith('[') or content.strip().startswith('exitcode')):
                if content not in [h[1] for h in st.session_state.history]:
                    st.session_state.history.append(("assistant", content))
                    new_messages_found = True

        elif name == "Event_Recommendation_Agent":
            # always append whatever markdown/code it spits out
            if content not in [h[1] for h in st.session_state.history]:
                st.session_state.history.append(("assistant", content))
                new_messages_found = True
        
    # If new messages were found, trigger a rerun
    return new_messages_found


# Add a custom message validator to prevent duplicates
def message_validator(messages):
    if len(messages) > 1:
        last_message = messages[-1].get("content", "")
        second_last = messages[-2].get("content", "") if len(messages) > 1 else ""
        
        # Prevent exact duplicate messages
        if last_message == second_last:
            return False
    return True

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
    st.session_state.processed_indices = set()
    st.session_state.displayed_questions = set()

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

    group_chat.message_validator = message_validator
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



# Continuous message checking
if st.session_state.initialized and "manager" in st.session_state:
    # Check for unprocessed messages
    if hasattr(st.session_state.manager.groupchat, 'messages'):
        total_messages = len(st.session_state.manager.groupchat.messages)
        processed_count = len(st.session_state.processed_indices) if "processed_indices" in st.session_state else 0
        
        if total_messages > processed_count:
            print(f"Found {total_messages - processed_count} unprocessed messages")
            process_chat_messages()

# Display chat history
for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)


# Chat input
user_input = st.chat_input("Type your message here...")

if user_input:
    # Add user message to history and display it
    st.session_state.history.append(("user", user_input))
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Set flag to indicate we're waiting for response
    st.session_state.waiting_for_response = True
    
    # Process the message
    with st.spinner("Processing your request..."):
        try:
            if not st.session_state.chat_started:
                # Start the group chat
                st.session_state.chat_started = True
                
                # Clear any previous processing state
                if "processed_indices" in st.session_state:
                    st.session_state.processed_indices = set()
                if "displayed_questions" in st.session_state:
                    st.session_state.displayed_questions = set()
                
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
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check your API keys and try again.")
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()

    st.rerun()


# Sidebar
with st.sidebar:
    st.header("Steps to Plan Your Event")
  
    st.markdown("---")
    st.markdown("### Steps:")
    st.markdown("1. What type of event are you planning? ")
    st.markdown("2. How many participants will be attending? ")
    st.markdown("3. What is your budget per person? ")
    st.markdown("4. What date and time is the event? ")
    st.markdown("5. Where is the event located? ")
    st.markdown("6. Do you have any special requests or dietary requirements? ")
    st.markdown("7. I'll find the perfect venues for you!")
    