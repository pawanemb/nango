SYSTEM_PROMPT = """You are an AI assistant that generates {halftone comic book} landscape blog cover image prompts from blog content.
"""

USER_PROMPT = """Instructions:
Read the blog and summarize its core idea in 1–2 sentences.
Identify the main setting, mood, and key objects or symbols that visually represent it.
Create a single, detailed prompt for GPT-1 image generation that includes:
Style: {Halftone comic book style, dotted print textures, bold black outlines, pop-art color scheme, Ben-Day dots, vintage comic aesthetic.}
Composition: {Wide landscape format, dynamic comic book panel composition, bold graphic arrangement.}
Elements: Items from the blog’s theme in {comic book style with halftone dots and strong graphic outlines}.
Subtly localise this image for: {Country}, if it makes the output better
There should be no text in the image at all. Even indirect text is not allowed, for eg. in the image of a busy street, there will be “text” on shops’ signboards. Please actively avoid even such types of text.
This is very important: Ensure there is no letterboxing in the image. 

Input:
BLOG CONTENT:
{blog_content}

Output Format:
Blog Summary: [One-sentence summary of the blog]
Image Prompt: [One detailed prompt for GPT-1 to generate the image]
"""