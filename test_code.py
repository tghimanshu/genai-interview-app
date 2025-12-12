# DEFAULT_RESUME_TEXT = open("himanshu-resume.txt", "r", encoding="utf-8").read()
# DEFAULT_JOB_DESCRIPTION_TEXT = open("SDE_JD.txt", "r", encoding="utf-8").read()

# resume_text = DEFAULT_RESUME_TEXT.strip()
# jd_text = (DEFAULT_JOB_DESCRIPTION_TEXT).strip()
# prompt_context = """
# Score the candidate based on the following criteria:
# 1. Technical Skills: Evaluate the candidate's proficiency in relevant technical skills and knowledge.
# 2. Problem-Solving Ability: Assess the candidate's ability to analyze and solve problems effectively.
# 3. Communication Skills: Rate the candidate's ability to communicate ideas clearly and effectively.
# 4. Cultural Fit: Determine how well the candidate aligns with the company's values and culture.
# 5. Overall Impression: Provide an overall score based on the candidate's performance during the interview.

# Give reasons and key takeaways for each criteria. Provide separate scores (out of 10) for resume match and interview performance, then give a final averaged score out of 10.
# FORMAT: ```json
# {
# "technical_skills": {
# "score": int,
# "reasoning": str,
# },
# "problem_solving_ability": {
# "score": int,
# "reasoning": str,
# },
# "communication_skills": {
# "score": int,
# "reasoning": str,
# },
# "cultural_fit": {
# "score": int,
# "reasoning": str,
# },
# "overall_impression": {
# "score": int,
# "reasoning": str,
# },
# }
# """
# from google import genai
# from google.genai import types as genai_types

# client = genai.Client(api_key="AIzaSyC-bsNR-O_nJHT_oqvKRysrT0tMgzPcVxo")

# response = client.models.generate_content(
#     model="gemini-2.5-flash",
#     contents={
#         "role": "user",
#         "parts": [
#             genai_types.Part.from_text(
#                 text=open(
#                     r"recordings\session_20251119_090821_formatted_transcript.txt",
#                     "r",
#                     encoding="utf-8",
#                 ).read()
#             ),
#             genai_types.Part.from_text(text=resume_text),
#             genai_types.Part.from_text(text=jd_text),
#             genai_types.Part.from_text(text=prompt_context),
#         ],
#     },
# )

# my_score = response.text.split("```json")[-1]
# my_score = my_score.split("```")[0]

# with open(
#     "recordings\session_20251119_090821_score.txt", "w", encoding="utf-8"
# ) as score_path:
#     score_path.write(response.text or "")

import sqlite3

from database_operations import InterviewDatabaseOps

db_ops = InterviewDatabaseOps("./db/interview_database.db")
db_ops.update_interview_using_session_id(
    "interview_1763543218629_2lhlhw1r0",
    {
        "interviewer_notes": open(
            "recordings/session_20251119_090821_score.json", "r", encoding="utf-8"
        ).read(),
        "status": "completed",
    },
)
