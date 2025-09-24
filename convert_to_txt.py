import os
import pathlib

from google.genai import Client, types


def convert_to_txt(input_file):
    client = Client(api_key=os.environ.get("GENAI_API_KEY", "<Enter your API key here>"))
    prompt_file = client.files.upload(file=input_file)
    response = client.models.generate_content(
        model="gemini-2.5-pro",
       contents=[
               prompt_file,
                f"""
                SYSTEM: ```You are a helpful assistant that converts the content of the provided Resume or CV into plain text format.```

                INSTRUCTIONS: ```
                * Extract all text content from the provided Resume or CV.
                * Ignore any images, graphics, or non-text elements.
                * Ensure to format the text in a clear and readable manner.
                * Ensure Name, Contact Information, Skills, Experience, and Education are clearly labeled.
                * Output the content in plain text format without any special formatting or markup.
                ```

                OUTPUT: ```text

                The content of the Resume or CV in plain text format.

                ```
                """
            ]
    )

    output_text = response.text
    with open( input_file.split(".")[0] + ".txt", "w") as f:
        f.write(output_text)
    print("Conversion complete. Output saved to", input_file.split(".")[0] + ".txt")

convert_to_txt("himanshu-resume.pdf")