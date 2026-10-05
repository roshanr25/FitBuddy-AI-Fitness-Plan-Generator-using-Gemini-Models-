from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database import (
    get_db, save_user, save_plan, update_plan, 
    get_user, get_original_plan, get_all_users
)
from .models import WorkoutPlan

from .gemini_generator import generate_plan_and_tip
from .updated_plan import get_updated_plan

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/generate-workout", response_class=HTMLResponse)
async def create_workout(
    request: Request,
    username: str = Form(...),
    user_id: str = Form(...),
    age: int = Form(...),
    height: int = Form(...),
    weight: int = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
    db: Session = Depends(get_db)
):
    generated_data = generate_plan_and_tip(age, weight, goal, intensity)
    plan = generated_data.get("workout_plan", "Error generating plan.")
    tip = generated_data.get("nutrition_tip", "Error generating tip.")
    
    # Database logic
    user = get_user(db, user_id)
    if not user:
        user = save_user(db, user_id, username, age, height, weight, goal, intensity)
    else:
        # Update user specifics
        user.age = age
        user.height = height
        user.weight = weight
        user.goal = goal
        user.intensity = intensity
        db.commit()
        db.refresh(user)
        
    wp = save_plan(db, user.id, plan, tip)
    
    return templates.TemplateResponse("result.html", {
        "request": request, 
        "user_id": user_id,
        "username": username,
        "age": age,
        "height": height,
        "weight": weight,
        "goal": goal,
        "intensity": intensity,
        "plan": plan, 
        "tip": tip,
        "wp_id": wp.id
    })

@router.post("/submit-feedback", response_class=HTMLResponse)
async def submit_feedback(
    request: Request,
    wp_id: int = Form(...),
    feedback: str = Form(...),
    db: Session = Depends(get_db)
):
    original_plan = get_original_plan(db, wp_id)
    
    # Get the parent workout plan details
    wp = db.query(WorkoutPlan).filter(WorkoutPlan.id == wp_id).first()
    
    if wp and original_plan:
        updated_plan_text = get_updated_plan(original_plan, feedback)
        update_plan(db, wp_id, updated_plan_text)
        
        user = wp.user
        
        return templates.TemplateResponse("result.html", {
            "request": request,
            "user_id": user.user_id,
            "username": user.username,
            "age": user.age,
            "weight": user.weight,
            "goal": user.goal,
            "intensity": user.intensity,
            "plan": updated_plan_text,
            "tip": wp.nutrition_tip,
            "wp_id": wp.id
        })
        
    return HTMLResponse("Error: Workout plan not found.", status_code=404)

@router.get("/view-all-users", response_class=HTMLResponse)
async def view_all_users(request: Request, db: Session = Depends(get_db)):
    users = get_all_users(db)
    return templates.TemplateResponse("all_users.html", {"request": request, "users": users})
