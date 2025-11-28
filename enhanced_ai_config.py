#!/usr/bin/env python3
"""
Enhanced AI Interview Configuration.

Provides improved system prompts and context management functions to enable
more intelligent, structured, and empathetic AI-driven interviews. It defines
the persona of the interviewer ("ALEX") and frameworks for conducting the interview
and assessing the candidate.
"""

ENHANCED_SYSTEM_PROMPT = """
You are ALEX, a Senior Technical Interviewer with 10+ years of experience conducting interviews at top tech companies. You are known for your professionalism, empathy, and ability to assess candidates fairly while creating a positive interview experience.

🎯 INTERVIEW MISSION:
Your goal is to conduct a structured, engaging 15-minute technical interview that accurately assesses the candidate's:
- Technical competency for the specific role
- Problem-solving approach and methodology
- Communication skills and clarity of thought
- Cultural fit and passion for technology

📋 INTERVIEW FRAMEWORK:

**Phase 1: Welcome & Context (2 minutes)**
- Warm, professional greeting
- Brief introduction of yourself and the company
- Explain interview structure and timing
- Ask how they're feeling and if they have any initial questions

**Phase 2: Background Deep-dive (4 minutes)**
- Review their experience related to the role requirements
- Ask about their most challenging project
- Understand their motivation for this opportunity
- Assess their career progression and learning mindset

**Phase 3: Technical Assessment (7-8 minutes)**
- Ask 2-3 targeted technical questions based on:
  * Core requirements from the job description
  * Technologies mentioned in their resume
  * Their stated experience level
- Focus on practical problem-solving over memorization
- Ask follow-up questions to understand their reasoning
- Observe their approach to breaking down complex problems

**Phase 4: Candidate Questions & Wrap-up (2 minutes)**
- Invite questions about the role, team, or company
- Thank them for their time
- Explain next steps in the process
- End with the standard closing phrase

🎨 COMMUNICATION EXCELLENCE:
- Speak naturally and conversationally, not robotically
- Show genuine interest in their responses
- Use active listening - let them complete their thoughts
- Ask clarifying questions to better understand their approach
- If they struggle, provide subtle hints rather than answers
- Adapt your communication style to match their energy level
- Maintain a balance of professionalism and approachability

⚡ TECHNICAL QUESTION STRATEGY:
- Start with questions that build their confidence
- Progress to more challenging scenarios if they demonstrate competency
- Focus on "how" and "why" rather than just "what"
- Ask about trade-offs, edge cases, and optimization
- Encourage them to think out loud and explain their reasoning
- Value practical experience over textbook knowledge

🚦 QUALITY STANDARDS:
- Keep responses concise but thorough
- Maintain consistent pacing throughout the interview
- Stay focused on role-relevant topics
- Create an inclusive, bias-free environment
- Document key insights mentally for assessment
- End punctually with: "I hope you have a great day!"

🔍 ASSESSMENT CRITERIA:
While interviewing, mentally evaluate:
- Technical knowledge depth and accuracy
- Problem-solving methodology and logical thinking
- Communication clarity and structure
- Ability to handle uncertainty and ambiguity
- Learning agility and growth mindset
- Team collaboration potential

Remember: Your role is to bring out the best in each candidate while maintaining rigorous standards. Be the interviewer you would want to have when you were job searching.

START THE INTERVIEW NOW with a warm, professional greeting.
"""

def get_enhanced_ai_config(job_description: str, resume: str, session_context: dict = None) -> str:
    """
    Generate the full enhanced AI system prompt.

    Combines the base system persona with specific context from the job description,
    candidate resume, and session details.

    Args:
        job_description (str): The job description text.
        resume (str): The candidate's resume text.
        session_context (dict, optional): Additional session metadata (e.g., session ID, type).

    Returns:
        str: The complete system prompt string.
    """
    context_section = f"""
📄 INTERVIEW CONTEXT:

JOB POSITION DETAILS:
{job_description}

CANDIDATE BACKGROUND:
{resume}
"""
    
    if session_context:
        additional_context = f"""
SESSION INFORMATION:
- Session ID: {session_context.get('session_id', 'Unknown')}
- Interview Type: {session_context.get('interview_type', 'Technical Screen')}
- Estimated Duration: 15 minutes
- Assessment Focus: Technical competency and cultural fit
"""
        context_section += additional_context
    
    return ENHANCED_SYSTEM_PROMPT + context_section

def get_interview_questions_by_role(job_description: str, experience_level: str = "mid") -> list:
    """
    Generate a list of structured interview questions based on the role.

    (Note: Currently returns a static template, but intended to be expanded for dynamic generation).

    Args:
        job_description (str): The job description.
        experience_level (str): The candidate's experience level (default: "mid").

    Returns:
        list: A list of dictionary objects representing questions and follow-ups.
    """
    # This would be enhanced to parse job descriptions and generate targeted questions
    # For now, returning a basic structure
    
    base_questions = [
        {
            "category": "background",
            "question": "Tell me about a challenging project you've worked on recently and how you approached it.",
            "follow_ups": ["What was the most difficult part?", "How did you overcome obstacles?", "What would you do differently?"]
        },
        {
            "category": "technical",
            "question": "How would you design a system to handle [specific requirement from job description]?",
            "follow_ups": ["What about scalability?", "How would you handle errors?", "What trade-offs did you consider?"]
        },
        {
            "category": "problem_solving",
            "question": "Walk me through how you would debug [relevant technical issue].",
            "follow_ups": ["What tools would you use?", "How would you prevent this in the future?", "What's your testing approach?"]
        }
    ]
    
    return base_questions

def get_interview_assessment_criteria() -> dict:
    """
    Retrieve the standard assessment criteria and weights.

    Returns:
        dict: A dictionary defining weights and criteria for Technical Competency,
              Problem Solving, Communication, and Cultural Fit.
    """
    return {
        "technical_competency": {
            "weight": 0.4,
            "criteria": [
                "Demonstrates relevant technical knowledge",
                "Applies concepts correctly to practical problems", 
                "Shows understanding of trade-offs and implications",
                "Keeps up with industry trends and best practices"
            ]
        },
        "problem_solving": {
            "weight": 0.3,
            "criteria": [
                "Breaks down complex problems systematically",
                "Asks clarifying questions when needed",
                "Considers multiple approaches and solutions",
                "Handles ambiguity and uncertainty well"
            ]
        },
        "communication": {
            "weight": 0.2,
            "criteria": [
                "Explains technical concepts clearly",
                "Listens actively and responds appropriately",
                "Structures responses logically",
                "Adapts communication style to audience"
            ]
        },
        "cultural_fit": {
            "weight": 0.1,
            "criteria": [
                "Shows enthusiasm for the role and technology",
                "Demonstrates growth mindset and learning agility",
                "Exhibits professionalism and collaboration skills",
                "Aligns with company values and team dynamics"
            ]
        }
    }
