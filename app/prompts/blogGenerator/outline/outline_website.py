from typing import List

def outline_website_prompt(
        scrapped_content: str,
    ) -> str:
        """Generate prompt for creating blog outline."""
        print(f"DEBUG: Received content length: {len(scrapped_content)}")
        
        prompt = f"""

Input: 
Scrapped Markdown of Article Webpage: {scrapped_content}

Goal: 
Export the outline of the blog from the input which is a scrapped blog webpage in markdown format.

Process:
Step 1, Cleaning- The input which is the scrapped markdown of a blog webpage has a lot of unnecessary content like menu bar text, webpage URL, blog author name, blog publish date, images meta data etcetera. Ignore all of this and extract the clean text of the blog. Make sure to not alter any blog text, do not add any of your comments or interpretations. It is important for the success of the task to extract the clean and unaltered version of the blog content.
Step 2, Understand the different elements of markdown language- Markdown is a lightweight markup language used to format plain text for web content, documentation, and more. It includes various elements to structure and style text efficiently. Headings are created using # symbols, with # for H1, ## for H2, and so on up to ###### for H6. Lists can be either unordered, using -, *, or +, or ordered, using numbers followed by a period (1.). Tables are defined using pipes (|) to separate columns and hyphens (-) to define headers, such as | Column 1 | Column 2 | followed by | --- | --- |. Blockquotes are indicated by a > at the beginning of a line, allowing for nested quotes by using multiple > symbols. Code blocks can be inline using backticks (`code`) or multi-line by enclosing text within triple backticks ( ). Bold and italic text is created using **bold**, *italic*, or __bold__ and _italic_, respectively. Links are formatted as [text](URL), while images use the same syntax but with an exclamation mark: ![alt text](imageURL). Horizontal rules are made using ---, ***, or ___ on a new line. Markdown also supports inline HTML, automatic link detection, and various extensions depending on the renderer, making it a flexible and widely-used formatting tool.
Step 3, Sectional Headings (H2) and Sub-Headings (H3) extraction- Thoroughly read the entire post and identify all Sectional Headings (H2) and Sub-Headings (H3) and Sub-Sub Headings (H4). Organize them by placing each Sub-Headings (H3) directly under its corresponding Sectional Headings (H2), maintaining the original order. Truncate all Sub-sub headings (H4) Ensure the final output is in plain text format, accurately reflecting the structure of Sectional Headings (H2) and Sub-Headings (H3) of the original blog post. Ignore Sub-sub headings (H4) and beyond. Do not include the text contained within the Sectional Headings (H2) or Sub-Headings (H3).
Step 4, Convert in markdown format- Convert the organised Sectional Headings (H2) and Sub-Headings (H3) in a markdown format. Make sure to not change any text. Use verbatim text from Step 2. 
Step 5,Final Check- Ensure that the markdown output has accurately labelled the Sectional Headings (H2) and Sub-Headings (H3) by reading through the blog again. Ensure all Sub-sub headings (H4) are removed from the final output.

Output:
Give output in json format.
Do not add any comments from your end.
Do not reduce any text.
Do not include Sub-sub headings (H4) in the final output.
Don't include ```json``` in the output.
Give FAQs after the conclusion.
Give Conclusion before the FAQs.
When giving output, do not write “```json”

Put subsections between []

Output:	
Give the output in the JSON format.
Do not give explanations of the headings and subheadings.
Do not acknowledge the completion of the task in your response. 
Give FAQs after the conclusion.
Give Conclusion before the FAQs.
When giving output, do not write "```json" or "```"
Remove the markdown formatting and other special symbols from the output. 
Do not include em dash (—) and n-dash ( – ) anywhere in your response strictly. This is critical for the success of the task.
Don’t give numbers to headings or subheadings in your response.




Please provide the outline in the following JSON format:
{{
  "outline": {{
    "sections": [
      {{
        "heading": "Main Section Heading",
        "subsections": [
          "Subsection 1",
          "Subsection 2",
          "Subsection 3"
        ]
      }}
    ],
    "conclusion": {{
      "heading": "Conclusion Title"
    }},
    "faqs": {{
      "heading": "Frequently Asked Questions",
      "questions": [
        "Relevant FAQ Question 1",
        "Relevant FAQ Question 2",
        "Relevant FAQ Question 3"
      ]
    }}
  }}
}}


"""
        return prompt