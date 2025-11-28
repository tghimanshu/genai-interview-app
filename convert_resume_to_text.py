"""
Resume Conversion Utility.

This module provides functionality to convert resumes (PDF, image, etc.) into structured
JSON data using the Gemini API. It extracts key details such as candidate name,
contact info, skills, experience, and education.
"""

import os
import pathlib
import json

from google.genai import Client, types
from dotenv import load_dotenv
load_dotenv()


def convert_resume_to_txt(input_file):
    """
    Convert a resume file to structured JSON data.

    Uploads the file to Gemini and prompts it to extract specific fields.

    Args:
        input_file (str): The path to the resume file.

    Returns:
        dict: A dictionary containing extracted resume details, including:
              candidate_name, resume_text, email, phone, skills, experience_years,
              education, certifications, linkedin_url, and portfolio_url.
              Returns None if the conversion fails.
    """
    try:
        client = Client(api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"))
        prompt_file = client.files.upload(file=input_file)
        response = client.models.generate_content(
            model="gemini-2.5-pro",
        contents=[
                prompt_file,
                    """
                    SYSTEM: ```You are a helpful assistant that converts the content of the provided Resume or CV into plain text format.```

                    INSTRUCTIONS: ```
                    * Extract all key details from the provided Resume or CV.
                    * Ignore any images, graphics, or non-text elements.
                    * Ensure to format the text in a clear and readable manner.
                    * Ensure Name, Contact Information, Skills, Experience, and Education are clearly labeled.
                    * Output the content in plain text format without any special formatting or markup.
                    ```

                    EXAMPLE OUTPUT: ```json
                    {
                        "candidate_name": "Extracted Name",
                        "resume_text": "Extracted resume text",
                        "email": "extracted email e.g. email@example.com",
                        "phone": "123-456-7890",
                        "skills": "extracted skills as JSON string",
                        "experience_years": 5,
                        "education": "extracted education details",
                        "certifications": "extracted certifications",
                        "linkedin_url": "https://www.linkedin.com/in/extracted-linkedin",
                        "portfolio_url": "https://www.portfolio.com/in/extracted-portfolio",
                    }
                    ```
                    """
                ]
        )

        output_text = response.text
        output_json = json.loads(output_text[output_text.find("{"):output_text.rfind("}") + 1])
        return output_json
    except Exception as e:
        print(f"Error converting resume to text: {e}")
        return None

# convert_to_txt("himanshu-resume.pdf")
