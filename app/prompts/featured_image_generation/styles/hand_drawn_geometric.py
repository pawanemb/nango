SYSTEM_PROMPT = """You are an AI assistant that generates {Hand-drawn Geometric Illustration} landscape blog cover image prompts from blog content.

"""

USER_PROMPT = """
Instructions:
Read the blog and summarize its core idea in 1–2 sentences.
Identify the main setting, mood, and key objects or symbols that visually represent it.
Create a single, detailed prompt for GPT-1 image generation that includes:
Style: {Hand-drawn geometric illustration, vibrant saturated colors with visible brushwork, flat design with subtle irregularities in shapes, paper cut-out aesthetic with soft uneven edges, naive art influence, bold color blocking with organic boundaries, shapes that feel cut by hand rather than computer-generated, playful folk art quality, slight imperfections that add warmth and character, matte finish without digital polish.}
Composition:{Wide landscape format, intuitively balanced layout with organic flow, layered depth using overlapping hand-cut shapes, gently curved lines and soft geometric forms, focal point with charmingly imperfect supporting elements, breathing room between elements, perspective that feels observed rather than constructed, natural arrangement as if pieces were placed by hand, slightly asymmetrical for visual interest.}
Elements: {Main subject simplified but with hand-drawn character, organic geometric shapes with soft wobbly edges, trees and objects that feel sketched then filled with solid color, paths and roads with gentle hand-drawn curves, elements that appear cut from colored paper, visible human touch in every shape, folk art inspired motifs, colors that slightly bleed outside implied lines, childlike simplicity with sophisticated color choices, imperfect repetition in repeated elements.}
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