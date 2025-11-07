from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
from datetime import datetime

app = FastAPI(title="HerSafe API", version="1.0.0")

# Enable CORS for React Native
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Emergency contacts
EMERGENCY_CONTACTS = {
    "Police Emergency": "999",
    "Women Helpline": "109",
    "Ambulance": "199",
    "Legal Aid": "16430",
    "Crisis Center": "10921",
    "Chittagong Police": "031-619101"
}

CHITTAGONG_AREAS = {
    "safe": ["Agrabad", "GEC Circle", "Nasirabad", "Panchlaish", "CDA Avenue"],
    "moderate": ["New Market", "Chawkbazar", "Sadarghat", "Reazuddin Bazar"],
    "caution_night": ["Halishahar", "Bahaddarhat", "Katalganj"]
}

# Pydantic models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    feature: Optional[str] = "assistant"  # assistant, legal, mental, route, sos
    groq_api_key: str

class RouteRequest(BaseModel):
    start_location: str
    end_location: str
    groq_api_key: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str

class RouteResponse(BaseModel):
    analysis: str
    maps_link: Optional[str]
    safety_status: str
    timestamp: str

class SafetyStatusResponse(BaseModel):
    status: str
    color: str
    advice: str
    timestamp: str

# Helper functions
def get_safety_status():
    """Get current safety status based on time"""
    hour = datetime.now().hour
    timestamp = datetime.now().strftime('%I:%M %p, %B %d, %Y')
    
    if hour >= 22 or hour <= 5:
        return "🔴 HIGH ALERT", "red", "Very late/early hours - Avoid travel if possible", timestamp
    elif hour >= 20 or hour <= 6:
        return "🟠 CAUTION", "orange", "Night time - Use well-lit roads, inform someone", timestamp
    elif hour >= 18:
        return "🟡 MODERATE", "yellow", "Evening - Stay on busy streets", timestamp
    return "🟢 SAFE", "green", "Daytime - Generally safer, stay alert", timestamp

def get_system_prompt(feature: str) -> str:
    """Get system prompt based on feature"""
    base = f"""You are SafeHer AI, a women's safety assistant for Chittagong, Bangladesh.
Current time: {datetime.now().strftime('%I:%M %p, %B %d, %Y')}
Location: Chittagong, Bangladesh
Emergency Contacts:
- Police: 999
- Women Helpline: 109
- Ambulance: 199
- Legal Aid: 16430
- Crisis Center: 10921
"""
    
    if feature == "legal":
        return base + """
FOCUS: Legal Rights & Harassment Laws
Key Bangladesh Laws:
1. Sexual Harassment at Workplace Act 2009
   - Penalties: Up to 5 years + BDT 50,000 fine
2. Women and Children Repression Prevention Act 2000
   - Death penalty or life imprisonment for serious offenses
3. Domestic Violence Prevention Act 2010
   - Protection orders, residence orders, monetary relief
4. Dowry Prohibition Act 1980
   - Up to 5 years + BDT 1,00,000 fine
How to Report:
- Police Station: File FIR
- One-Stop Crisis Center: Chittagong Medical College Hospital
- Legal Aid: Call 16430 (free)
Provide clear, actionable legal guidance."""

    elif feature == "mental":
        return base + """
FOCUS: Mental Health & Trauma Support
Immediate self-help:
1. Grounding (5-4-3-2-1)
2. Deep breathing (4-7-8)
3. Self-compassion
Support in Bangladesh:
- Crisis Center: 10921
- Kaan Pete Roi: 09678 676 778
Provide empathetic, validating support."""

    elif feature == "route":
        return base + """
FOCUS: Route Safety & Navigation
Chittagong Safe Areas:
- Generally Safe: Agrabad, GEC Circle, Nasirabad, Panchlaish
- Moderate: New Market, Chawkbazar, Sadarghat
- Caution at Night: Halishahar, Bahaddarhat, Katalganj
Provide specific route advice for Chittagong."""

    elif feature == "sos":
        return base + """
FOCUS: Emergency SOS Protocol
IMMEDIATE DANGER - DO THIS NOW:
1. CALL FOR HELP - Police: 999, Women Helpline: 109
2. GET TO SAFETY - Run towards lights, crowds
3. SHARE LOCATION
4. MAKE NOISE
Provide urgent, clear, step-by-step instructions."""

    else:  # assistant
        return base + """
FOCUS: General Women's Safety Assistant
Be empowering, culturally sensitive, and action-oriented."""

def call_groq_api(message: str, history: List[ChatMessage], groq_api_key: str, feature: str) -> str:
    """Call Groq API for chat completion"""
    try:
        # Build messages
        messages = [{"role": "system", "content": get_system_prompt(feature)}]
        
        # Add history (last 10 messages)
        for msg in history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # Call Groq API
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key.strip()}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            raise HTTPException(status_code=response.status_code, 
                              detail=f"Groq API Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def create_google_maps_link(start: str, end: str) -> str:
    """Create Google Maps directions link"""
    start_encoded = start.replace(" ", "+") + ",+Chittagong,+Bangladesh"
    end_encoded = end.replace(" ", "+") + ",+Chittagong,+Bangladesh"
    return f"https://www.google.com/maps/dir/?api=1&origin={start_encoded}&destination={end_encoded}&travelmode=walking"

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "HerSafe API - Women's Safety Assistant",
        "version": "1.0.0",
        "endpoints": {
            "POST /chat": "General chat with AI assistant",
            "POST /route-safety": "Analyze route safety",
            "GET /safety-status": "Get current safety status",
            "GET /emergency-contacts": "Get emergency contact numbers"
        }
    }

@app.get("/safety-status", response_model=SafetyStatusResponse)
async def safety_status():
    """Get current safety status based on time"""
    status, color, advice, timestamp = get_safety_status()
    return SafetyStatusResponse(
        status=status,
        color=color,
        advice=advice,
        timestamp=timestamp
    )

@app.get("/emergency-contacts")
async def emergency_contacts():
    """Get emergency contact numbers"""
    return {
        "contacts": EMERGENCY_CONTACTS,
        "areas": CHITTAGONG_AREAS
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with SafeHer AI assistant
    
    Features: 
    - assistant: General safety assistant
    - legal: Legal rights and harassment laws
    - mental: Mental health support
    - route: Route safety (use /route-safety for detailed analysis)
    - sos: Emergency SOS protocol
    """
    if not request.groq_api_key:
        raise HTTPException(status_code=400, detail="Groq API key is required")
    
    response = call_groq_api(
        request.message,
        request.history,
        request.groq_api_key,
        request.feature
    )
    
    return ChatResponse(
        response=response,
        timestamp=datetime.now().strftime('%I:%M %p, %B %d, %Y')
    )

@app.post("/route-safety", response_model=RouteResponse)
async def route_safety(request: RouteRequest):
    """Analyze route safety between two locations in Chittagong"""
    if not request.start_location or not request.end_location:
        raise HTTPException(status_code=400, detail="Both start and end locations are required")
    
    if not request.groq_api_key:
        raise HTTPException(status_code=400, detail="Groq API key is required")
    
    status, color, advice, timestamp = get_safety_status()
    
    # Get AI analysis
    prompt = f"""Analyze the safety of this route in Chittagong:
From: {request.start_location}
To: {request.end_location}
Current time: {datetime.now().strftime('%I:%M %p')}
Provide:
1. Safety assessment for this specific route
2. Areas to be cautious about
3. Best path recommendations
4. Time-specific advice
5. Alternative routes if safer"""

    ai_response = call_groq_api(prompt, [], request.groq_api_key, "route")
    maps_link = create_google_maps_link(request.start_location, request.end_location)
    
    analysis = f"""Route Analysis: {request.start_location} → {request.end_location}
Current Time: {datetime.now().strftime('%I:%M %p, %B %d, %Y')}
Safety Status: {status}
General Advice: {advice}

AI Route Analysis:
{ai_response}"""
    
    return RouteResponse(
        analysis=analysis,
        maps_link=maps_link,
        safety_status=status,
        timestamp=timestamp
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
