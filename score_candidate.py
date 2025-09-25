from google import genai
import os

from google.genai import types
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
)


response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents={
        "role": "user",
        "parts": [
            types.Part.from_bytes(
                mime_type="text/plain",
                data=open("final_transcription.txt", "rb").read()
            ),
            types.Part.from_bytes(
                mime_type="text/plain",
                data=open("himanshu-resume.txt", "rb").read()
            ),
            types.Part.from_bytes(
                mime_type="text/plain",
                data=open("SDE_JD.txt", "rb").read()
            ),
            types.Part.from_text(
                text="""
Score the candidate based on the following criteria:
1. Technical Skills: Evaluate the candidate's proficiency in relevant technical skills and knowledge.
2. Problem-Solving Ability: Assess the candidate's ability to analyze and solve problems effectively
3. Communication Skills: Rate the candidate's ability to communicate ideas clearly and effectively.
4. Cultural Fit: Determine how well the candidate aligns with the company's values and culture.
5. Overall Impression: Provide an overall score based on the candidate's performance during the interview.

Give reasonings and key takeaways for each criteria. Provide a final score out of 10.
give Scores for resume match and interview performance separately and then take an average of both to give final score out of 10.
"""
            )
        ]
    }
)

# print("Response: ", response.text)
with open("final_evaluation.txt", "w", encoding="utf-8") as f:
    f.write(response.text)
    print("Final evaluation written to final_evaluation.txt")