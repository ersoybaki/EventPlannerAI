from dotenv import load_dotenv
from autogen import GroupChat, GroupChatManager
import os, sys, googlemaps
from agents import create_preference_agents
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


CODING_DIR = os.path.join(ROOT_DIR, "coding")
os.makedirs(CODING_DIR, exist_ok=True)

load_dotenv()
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("GOOGLEMAPS_API_KEY", None)

def custom_speaker_selection(last_speaker, groupchat):
    messages = groupchat.messages
    
    
    # Get the current state of collected information
    state = {
        "event_type": False,
        "participants": False,
        "budget": False,
        "time": False,
        "location": False,
        "special_requests": False,
        "fallback_choice_made": False,
        "waiting_for_fallback_details": False,
        "fallback_json_ready": False
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
            elif '{"fallback":' in content:
                state["fallback_json_ready"] = True

            # Fallback choice made
            elif content.strip() in ["1", "2", "3", "4", "5"] and any("Would you like me to try" in m.get("content", "") for m in messages[-3:]):
                state["fallback_choice_made"] = True

            # Check if recommendation agent is asking for fallback details
            elif any(phrase in content.lower() for phrase in [
                "how much larger should i search",
                "which nearby location would you like",
                "what's your new budget per person", 
                "what type of event would you like to try"
            ]):
                state["waiting_for_fallback_details"] = True
    
    
    selected_agent = None
    
    # If last speaker was proxy agent with user input, route appropriately
    if last_speaker and last_speaker.name == "Event_Preference_Proxy_Agent":
        # Check what the user input was
        user_msg = messages[-1].get("content", "") if messages else ""
        
        # Normal preference collection flow
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
        elif all(state[key] for key in ["event_type", "participants", "budget", "time", "location", "special_requests"]) and not any([state["fallback_choice_made"], state["waiting_for_fallback_details"], state["fallback_json_ready"]]):
            selected_agent = groupchat.agent_by_name("Code_Generator_Agent")
        
        # Fallback flow handling
        elif user_msg.strip() in ["1", "2", "3", "4", "5"]:
            selected_agent = groupchat.agent_by_name("Event_Recommendation_Agent")
        # User provided details for fallback 
        elif state["waiting_for_fallback_details"]:
            selected_agent = groupchat.agent_by_name("Event_Recommendation_Agent")
    
    # Handle preference agents
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
            
            if any(pattern in last_msg for pattern in ['{"event_type"', '{"participants"', '{"budget_per_person"', '{"event_time"', '{"location"', '{"special_requests"']):
                # Agent collected data, move to next
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
                elif all(state[key] for key in ["event_type", "participants", "budget", "time", "location", "special_requests"]):
                    selected_agent = groupchat.agent_by_name("Code_Generator_Agent")
            else:
                # Agent asking question, go to proxy
                selected_agent = groupchat.agent_by_name("Event_Preference_Proxy_Agent")
        
        # Handle code generation and execution
        elif last_speaker.name == "Code_Generator_Agent":
            selected_agent = groupchat.agent_by_name("Code_Executor_Agent")
            
        elif last_speaker.name == "Code_Executor_Agent":
            last_msg = messages[-1].get("content", "") if messages else ""
            if "No venues found" in last_msg or "Would you like me to try" in last_msg:
                # Code executor detected empty results and asked for fallback choice
                selected_agent = groupchat.agent_by_name("Event_Preference_Proxy_Agent")
            else:
                # Normal results, go to recommendations
                selected_agent = groupchat.agent_by_name("Event_Recommendation_Agent")
        
        elif last_speaker.name == "Event_Recommendation_Agent":
            last_msg = messages[-1].get("content", "") if messages else ""
            
            if '{"fallback":' in last_msg:
                # Recommendation agent provided fallback JSON, generate new code
                selected_agent = groupchat.agent_by_name("Code_Generator_Agent")
            elif any(phrase in last_msg.lower() for phrase in [
                "how much larger should i search",
                "which nearby location would you like",
                "what's your new budget per person",
                "what type of event would you like to try"
            ]):
                # Recommendation agent asked a question, wait for user input
                selected_agent = groupchat.agent_by_name("Event_Preference_Proxy_Agent")
            else:
                # End of conversation
                selected_agent = None
    
    # Start conversation
    if selected_agent is None and len(messages) == 0:
        selected_agent = groupchat.agent_by_name("Event_Type_Preference_Agent")
    
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
        
        
        # Skip empty messages
        if not content or content.strip() == "":
            continue
        
        # Skip coordinator agent messages
        if name == "Coordinator_Agent":
            continue
            
        # Skip proxy agent messages
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
                
                # Question/statement from the agent
                if line not in st.session_state.displayed_questions:
                    st.session_state.displayed_questions.add(line)
                    # Check if it's already in history
                    if line not in [h[1] for h in st.session_state.history]:
                        st.session_state.history.append(("assistant", line))
                        print(f"Added to history: {line}")
                        new_messages_found = True
                break
            
        elif name in ["Code_Generator_Agent", "Code_Executor_Agent"]:
            # Check for venue data FIRST, before skipping
            if name == "Code_Executor_Agent":
                content_stripped = content.strip()
                json_content = None

                # Handle different output formats
                # Format 1: "exitcode: 0 (execution succeeded)\nCode output:\n[JSON]"
                if "exitcode:" in content_stripped and "Code output:" in content_stripped:
                    parts = content_stripped.split("Code output:", 1)
                    if len(parts) > 1:
                        json_content = parts[1].strip()
                # Format 2: Direct JSON output
                elif content_stripped.startswith('['):
                    json_content = content_stripped
                
                if json_content and json_content.startswith('[') and json_content.endswith(']'):
                    try:
                        import json
                        venues_data = json.loads(json_content)
                                
                        # Verify it's a list of venue objects
                        if (isinstance(venues_data, list) and 
                            len(venues_data) > 0 and 
                            all(isinstance(v, dict) and 'name' in v for v in venues_data)):
                            
                            # Store venues for map display
                            st.session_state.current_venues = venues_data
                            st.session_state.show_map = True
                            print(f"Captured {len(venues_data)} venues for map display")
                            
                            # Debug first venue
                            first_venue = venues_data[0]
                            print(f"First venue: {first_venue.get('name', 'Unknown')}")
                            if 'geometry' in first_venue and 'location' in first_venue['geometry']:
                                loc = first_venue['geometry']['location']
                                print(f"Location: lat={loc.get('lat')}, lng={loc.get('lng')}")
                            else:
                                print("Warning: First venue missing geometry data")
                                
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse venue JSON: {e}")
                    except Exception as e:
                        print(f"Error processing venues: {e}")
            
            # regular skipping for display purposes
            if not (content.strip().startswith('{') or 
                   content.strip().startswith('[') or 
                   content.strip().startswith('exitcode') or
                   content.strip().startswith('```')):
                if content not in [h[1] for h in st.session_state.history]:
                    st.session_state.history.append(("assistant", content))
                    new_messages_found = True

        elif name == "Event_Recommendation_Agent":
            # show everything except JSON
            if not content.strip().startswith('{'):
                if content not in [h[1] for h in st.session_state.history]:
                    # Check if this is the venue recommendations then add to history
                    if "Address:" in content and "Rating:" in content:
                        # Store recommendations separately instead of adding to history
                        st.session_state.venue_recommendations = content
                        st.session_state.show_map = True
                        print("Venue recommendations detected, enabling map display")
                    else:
                        # Add non-recommendation messages to history normally
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

def reset_session_state():
    """Reset all session state variables to restart the event planner"""
    keys_to_reset = [
        "initialized", "history", "chat_started", "coordinator_agent",
        "displayed_messages", "processed_indices", "displayed_questions",
        "current_venues", "show_map", "venue_recommendations", "manager",
        "proxy", "waiting_for_response"
    ]
    
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    
    # Reset shown set instead of deleting it
    st.session_state.shown = set()

def check_api_keys():
    # Check API Keys from session state
    openai_key = st.session_state.get("openai_api_key")
    google_key = st.session_state.get("google_api_key")
    return bool(openai_key and google_key)

def get_api_keys():
    # Get API keys
    openai_key = st.session_state.get("openai_api_key")
    google_key = st.session_state.get("google_api_key")
    return openai_key, google_key

# UI Setup
st.set_page_config(
    page_title="Event Planner AI",
    page_icon=":robot:",
    layout="wide",
)

# Side-by-side logo and title
col1, col2 = st.columns([1, 6]) 

with col1:
    st.image("logo.png", width=100)

with col2:
    st.markdown("# Event Planner AI")
    st.markdown("Let me help you plan your perfect event!")

# API Key Configuration Section
if not check_api_keys():
    st.warning(":warning: Please configure your API keys to use the Event Planner")
    
    with st.container():
        st.markdown("### API Key Configuration")
        st.markdown("Your API keys are stored only for this session and are not saved permanently.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            openai_key_input = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-...",
                help="Get your API key from https://platform.openai.com/api-keys",
                key="openai_key_input"
            )
        
        with col2:
            google_key_input = st.text_input(
                "Google Maps API Key",
                type="password",
                placeholder="AIza...",
                help="Get your API key from https://console.cloud.google.com/",
                key="google_key_input"
            )
        
        if st.button("Save API Keys", type="primary"):
            if openai_key_input and google_key_input:
                st.session_state.openai_api_key = openai_key_input
                st.session_state.google_api_key = google_key_input
                

                st.success(":white_check_mark: API keys configured successfully! The page will refresh.")
                st.rerun()
            else:
                st.error("Please provide both API keys")
    
    st.info(":bulb: **Why do I need API keys?**\n\n"
            "- **OpenAI API Key**: Powers the AI agents that help plan your event\n"
            "- **Google Maps API Key**: Finds and displays venue locations and information")
    
    # Stop until API keys provided
    st.stop()  

# Get API keys for use
openai_key, google_key = get_api_keys()

if google_key:
    os.environ["RUNTIME_GOOGLEMAPS_API_KEY"] = google_key

# Initialize Google Maps client with the API key
try:
    gmaps = googlemaps.Client(key=google_key)
except Exception as e:
    st.error(f"Failed to initialize Google Maps client: {str(e)}")
    if st.button("Reset API Keys"):
        if "openai_api_key" in st.session_state:
            del st.session_state.openai_api_key
        if "google_api_key" in st.session_state:
            del st.session_state.google_api_key
        st.rerun()
    st.stop()

# Configure LLM with the API key
llm_config = {
    "model": "gpt-4o-mini",  
    "api_key": openai_key
}

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.history = []
    st.session_state.chat_started = False
    st.session_state.coordinator_agent = None  
    st.session_state.displayed_messages = set()  
    st.session_state.processed_indices = set()
    st.session_state.displayed_questions = set()
    st.session_state.current_venues = None  
    st.session_state.show_map = False  
    st.session_state.venue_recommendations = None

if not st.session_state.initialized:
    try:
        # Create all agents with the provided API keys
        type_agent, participant_agent, budget_agent, time_agent, \
        location_agent, request_agent, proxy_agent, executor_agent, \
        generator_agent, recommendation_agent, coordinator_agent = create_preference_agents(
            openai_key=openai_key,
            google_key=google_key
        )

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
    except Exception as e:
        st.error(f"Failed to initialize agents: {str(e)}")
        st.error("Please check your API keys and try again.")
        if st.button("Reset API Keys"):
            if "openai_api_key" in st.session_state:
                del st.session_state.openai_api_key
            if "google_api_key" in st.session_state:
                del st.session_state.google_api_key
            st.rerun()
        st.stop()

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

if st.session_state.get("show_map", False) and st.session_state.get("current_venues"):
    map_container = st.container()
    with map_container:
        st.markdown("## Venue Locations")
        st.markdown("### Click on the markers to see venue details.")
        
        try:
            from helperFunctions import create_venue_map
            create_venue_map(st.session_state.current_venues)
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.write("Full error:", e)
            import traceback
            st.write(traceback.format_exc())

    if st.session_state.get("venue_recommendations"):
        with st.chat_message("assistant"):
            st.markdown("## Venue Recommendations")
        
            # Clean up the recommendation text
            recommendations = st.session_state.venue_recommendations
            
            # Remove any markdown code block indicators if present
            if recommendations.startswith("```markdown"):
                recommendations = recommendations.replace("```markdown", "", 1)
            if recommendations.endswith("```"):
                recommendations = recommendations.rsplit("```", 1)[0]
            
            # Remove TERMINATE if present
            recommendations = recommendations.replace("TERMINATE", "").strip()
            
            # Display the cleaned recommendations
            st.markdown(recommendations)
    
    # Reset the flags
    st.session_state.show_map = False
    st.session_state.venue_recommendations = None

# Chat input - THIS SHOULD COME AFTER THE MAP DISPLAY
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
    
    # Add API key status indicator
    if check_api_keys():
        st.success(":white_check_mark: API Keys Configured")

    
    # Add restart button at the top of sidebar
    if st.button("Restart New Event Planning", type="primary", use_container_width=True):
        reset_session_state()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### Steps:")
    st.markdown("1. What type of event are you planning? ")
    st.markdown("2. How many participants will be attending? ")
    st.markdown("3. What is your budget per person? ")
    st.markdown("4. What date and time is the event? ")
    st.markdown("5. Where is the event located? ")
    st.markdown("6. Do you have any special requests? ")
    st.markdown("7. I'll find the perfect venues for you!")