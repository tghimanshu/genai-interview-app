"""
Candidate Scoring Utility.

This script uses the Gemini API to evaluate a candidate's performance based on the
interview transcript, their resume, and the job description. It generates a detailed
score report covering technical skills, problem-solving, communication, and cultural fit.
"""

from google import genai
import os

from google.genai import types
from dotenv import load_dotenv
load_dotenv()

def score_candidate(transcript_path="final_transcription.txt", resume_path="himanshu-resume.txt", jd_path="SDE_JD.txt", output_path="final_evaluation.txt"):
    """
    Scores a candidate based on interview artifacts.

    Args:
        transcript_path (str): Path to the interview transcript.
        resume_path (str): Path to the candidate's resume.
        jd_path (str): Path to the job description.
        output_path (str): Path to save the evaluation report.
    """
    try:
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
        )

        # Check if files exist
        for path in [transcript_path, resume_path, jd_path]:
            if not os.path.exists(path):
                print(f"Error: File not found: {path}")
                return

        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents={
                "role": "user",
                "parts": [
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open(transcript_path, "rb").read()
                    ),
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open(resume_path, "rb").read()
                    ),
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open(jd_path, "rb").read()
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

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            print(f"Final evaluation written to {output_path}")

    except Exception as e:
        print(f"Error scoring candidate: {e}")

if __name__ == "__main__":
    score_candidate()
