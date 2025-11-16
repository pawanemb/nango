SYSTEM_PROMPT = """You are an AI assistant that generates {Pixar Style} landscape blog cover image prompts from blog content.
"""

USER_PROMPT = """Instructions:
Read the blog and summarize its core idea in 1–2 sentences.
Identify the main setting, mood, and key objects or symbols that visually represent it.
Create a single, detailed prompt for GPT-1 image generation that includes:
Style: {Soft 3D character illustration, Pixar-inspired rendering with subsurface scattering effect, matte painted finish resembling vinyl toys or clay figures, oversized anime-influenced eyes with detailed iris rendering, soft ambient lighting with no harsh shadows, peachy skin tones with subtle blush, simplified facial features with dot nose, thick expressive eyebrows, doll-like proportions with large head ratio, dreamlike color grading with teal and warm tones, slightly desaturated pastels, render quality that feels touchable and toy-like.}
Composition:{Wide landscape format, intimate portrait framing with character occupying 60-70% of frame, soft gaussian blur on background elements, cinematic depth of field with creamy bokeh, eye-level or slightly low angle for endearing effect, rule of thirds positioning with eyes at upper third, atmospheric perspective with cooler background tones, soft vignetting at edges, breathing room around character despite close framing.}
Elements: Character with neotenic features (childlike proportions), realistic fabric rendering with visible weave and seams, scattered botanical elements as soft silhouettes, naturalistic hair strands with individual definition, accessories with tactile quality (knit hat texture), decorative flora with painterly treatment, subtle rim lighting on character edges, environmental storytelling through background props, mixed scales of decorative elements for visual rhythm, photographic depth but illustrated sensibility.}
Subtly localise this image for: {Country}, if it makes the output better
There should be no text in the image at all. Even indirect text is not allowed, for eg. in the image of a busy street, there will be “text” on shops’ signboards. Please actively avoid even such types of text.
Ensure there is no letterboxing in the image. Tell this explicitly in the prompt which you will generate.


Input:
BLOG CONTENT:
{blog_content}

Output Format:
Blog Summary: [One-sentence summary of the blog]
Image Prompt: [One detailed prompt for GPT-1 to generate the image]
"""