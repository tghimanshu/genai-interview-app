import json

with open("transcriptions.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

    final_transcription = ""

    is_output = False
    is_input = False

    for line in lines:
        if "OUTPUT: " in line:
            if not is_output:
                is_output = True
                is_input = False
                final_transcription += "\n[Interviewer]: "
            json_str = line.split("OUTPUT: ")[1].strip()
            try:
                data = json.loads(json_str)
                final_transcription += data.get("text")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Original string: {json_str}")
        if "INPUT: " in line:
            if not is_input:
                is_output = False
                is_input = True
                final_transcription += "\n[Interviewee]: "
            json_str = line.split("INPUT: ")[1].strip()
            try:
                data = json.loads(json_str)
                final_transcription += data.get("text")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Original string: {json_str}")
    with open("final_transcription.txt", "w", encoding="utf-8") as out_f:
        out_f.write(final_transcription.strip())
