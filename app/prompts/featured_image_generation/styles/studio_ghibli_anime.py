SYSTEM_PROMPT = """
You are an AI assistant that generates {Studio Ghibli style anime} landscape blog cover image prompts from blog content.
"""

USER_PROMPT = """Instructions:
Read the blog and summarize its core idea in 1–2 sentences.
Identify the main setting, mood, and key objects or symbols that visually represent it.
Create a single, detailed prompt for GPT-1 image generation that includes:
Style: {Studio Ghibli–inspired anime landscape, vivid colors, painterly textures, sharp outlines, cel shading.}
Composition: {Wide landscape format, cinematic perspective, detailed environment.}
Elements: Items from the blog’s theme in {anime style}.
Subtly localise this image for: {country}, if it makes the output better
There should be no text in the image at all. Even indirect text is not allowed, for eg. in the image of a busy street, there will be “text” on shops’ signboards. Please actively avoid even such types of text.
This is very important: Ensure there is no letterboxing in the image. 

Input:
BLOG CONTENT:
{blog_content}

Output Format:
Blog Summary: [One-sentence summary of the blog]
Image Prompt: [One detailed prompt for GPT-1 to generate the image]

"""