SYSTEM_PROMPT = """You are an AI assistant that generates {knitted yarn textile art} landscape blog cover image prompts from blog content.
"""

USER_PROMPT = """Instructions:
Read the blog and summarize its core idea in 1–2 sentences.
Identify the main setting, mood, and key objects or symbols that visually represent it.
Create a single, detailed prompt for GPT-1 image generation that includes:
Style: {Knitted yarn textile art, soft woolen textures, chunky knit patterns, cozy handcrafted feel, warm fabric colors.}
Composition:  {Wide landscape format, layered knitted elements, textured fabric composition.}
Elements: Items from the blog’s theme in {knitted yarn style with visible stitches and woolen texture}.
Subtly localise this image for: {country} , if it makes the output better
There should be no text in the image at all. Even indirect text is not allowed, for eg. in the image of a busy street, there will be “text” on shops’ signboards. Please actively avoid even such types of text.
This is very important: Ensure there is no letterboxing in the image. 

Input:
BLOG CONTENT:
{blog_content}
"""