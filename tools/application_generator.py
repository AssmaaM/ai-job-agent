"""
application_generator.py
-------------------------
Tool: Application Generator
Uses the OpenAI API to create personalized, professional application materials:
  1. Cover Letter  – Formal, multi-paragraph letter tailored to the job
  2. LinkedIn Note – Short, friendly connection/outreach message (< 300 chars)

Both outputs are generated in a single API call for efficiency.
"""

import os
import json
from openai import OpenAI

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# System prompt for the application writer persona
SYSTEM_PROMPT = """You are an expert career coach and professional writer with 20+ years of experience 
crafting job applications. You specialize in writing compelling, personalized cover letters and 
LinkedIn outreach messages that get candidates noticed.

Your writing style is:
- Confident but not arrogant
- Specific and results-oriented (use numbers/metrics when available from the CV)
- Tailored to the company's culture and job requirements
- Natural and human – never generic or template-sounding

Respond ONLY with a valid JSON object (no markdown code blocks, no extra text):
{
  "cover_letter": "<full cover letter text with proper paragraphs using \\n\\n>",
  "linkedin_message": "<short LinkedIn message, maximum 300 characters, friendly and direct>"
}
"""


def generate_application(cv: str, job: dict) -> dict:
    """
    Generate a personalized cover letter and LinkedIn message for a given job.

    Args:
        cv  (str) : The candidate's CV as plain text.
        job (dict): The job posting dictionary.

    Returns:
        dict: {
            "cover_letter"    : str,
            "linkedin_message": str
        }
        On error, returns placeholder strings with the error message.
    """
    job_title       = job.get("title", "Unknown Position")
    job_company     = job.get("company", "the company")
    job_location    = job.get("location", "")
    job_description = job.get("description", "")
    job_salary      = job.get("salary", "")

    # Provide context about the job and the candidate
    user_message = f"""
Please write personalized application materials for the following job.

=== TARGET JOB ===
Title      : {job_title}
Company    : {job_company}
Location   : {job_location}
Salary     : {job_salary}
Description:
{job_description}

=== CANDIDATE CV ===
{cv}

Instructions:
1. Cover Letter: Write a 3-4 paragraph professional cover letter. 
   - Paragraph 1: Strong opening – express enthusiasm and how you found the role
   - Paragraph 2: Highlight 2-3 specific skills/experiences from the CV that match the job
   - Paragraph 3: Explain why you're excited about THIS company specifically
   - Paragraph 4: Professional closing with a call to action
   Address it to "Hiring Manager" if no specific contact is known.

2. LinkedIn Message: Write a concise, friendly outreach message (MAX 300 characters).
   Keep it natural – introduce yourself, mention the role, and invite a conversation.

Respond ONLY with the JSON object.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.7,          # Slightly higher temperature for more creative writing
            max_tokens=1200,
        )

        raw_content = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps in ```json ... ```
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
            raw_content = raw_content.strip()

        result = json.loads(raw_content)

        # Ensure both keys exist with fallback values
        cover_letter     = result.get("cover_letter", "Cover letter generation failed.")
        linkedin_message = result.get("linkedin_message", "LinkedIn message generation failed.")

        # Enforce LinkedIn character limit
        if len(linkedin_message) > 300:
            linkedin_message = linkedin_message[:297] + "..."

        return {
            "cover_letter":     cover_letter,
            "linkedin_message": linkedin_message,
        }

    except json.JSONDecodeError:
        return {
            "cover_letter":     f"Cover letter generation failed. Raw response:\n{raw_content[:300]}",
            "linkedin_message": "Message generation failed.",
        }

    except Exception as e:
        return {
            "cover_letter":     f"An error occurred: {str(e)}\n\nPlease verify your OPENAI_API_KEY.",
            "linkedin_message": f"Error: {str(e)}",
        }
