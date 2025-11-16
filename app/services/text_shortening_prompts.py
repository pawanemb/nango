"""
Text Shortening Prompts for Content Editing Service
Separate prompt management for better code organization and maintainability
"""

from typing import Dict, Any, Optional, List


class TextShorteningPrompts:
    """Centralized prompt management for text shortening and content editing"""

    @staticmethod
    def get_text_shortening_prompt(
        text_to_edit: str,
        preceding_words: str,
        succeeding_words: str,
        brand_tonality: str,
        primary_keyword: str,
        language: str,
        reduction_percentage: int = 30
    ) -> str:
        """
        Generate prompt for shortening text content while preserving key elements
        
        Args:
            text_to_edit: The main text content to be shortened
            preceding_words: Context from before the text (50 words)
            succeeding_words: Context from after the text (50 words)
            brand_tonality: Brand voice and tone guidelines
            primary_keyword: SEO keyword to preserve
            language: Target language for output
            reduction_percentage: Target reduction percentage (default 30%)
            
        Returns:
            str: Formatted prompt string for OpenAI processing
        """
        
        prompt = f"""
You are an experienced content Editor specializing in concise, impactful writing.

INPUT DETAILS:
1. Text to be edited: {text_to_edit}
2. Preceding 50 words: {preceding_words}
3. Succeeding 50 words: {succeeding_words}
4. Brand Tonality: {brand_tonality}
5. Primary Keyword: {primary_keyword}
6. Language: {language}

GOAL:
1. Reduce the length of the "Text to be edited" by {reduction_percentage}%.
2. Preserve the primary keyword "{primary_keyword}" wherever mentioned.
3. Keep changes to a minimum while maximizing impact.
4. Do not add facts or figures from your end.
5. Preserve all formatting <p>, <H3>, <H2>, <H1> tags exactly as they appear.

PROCESS:

The shortening process is a 3-phase process detailed below:

**Phase 1: Structural Compression** – Remove redundancy at the macro level

Phase 1, Step 1: Delete repetition: If the same idea is expressed twice in different words, keep the sharper one.
Phase 1, Step 2: Cut off-ramps: Remove tangents or subplots that don't directly serve the main message.
Phase 1, Step 3: Merge overlapping points: Combine similar sentences into a single, high-impact one.

Phase 1 Example: "Our platform is fast, efficient, and saves time for users."
becomes
"Our platform saves time with unmatched speed and efficiency."

**Phase 2: Sentence Compression** – Tighten at the micro level

Phase 2, Step 1: Replace phrases with single words
Phase 2, Step 2: Strip filler words: very, really, actually, basically, in fact
Phase 2, Step 3: Use active voice: Cuts length and adds energy
Phase 2, Step 4: Prune qualifiers unless essential (might, perhaps, somewhat)

Phase 2 Example: "It is important to note that this feature will help users."
becomes
"This feature helps users."

**Phase 3: Impact Refinement** – Keep only what earns its place

Phase 3, Step 1: Run the "So what?" test: If a word, sentence, or section doesn't directly add value, cut it.
Phase 3, Step 2: Focus on the core promise: Readers should still get the full message even if they skim.
Phase 3, Step 3: Prioritize numbers & specifics over vague claims.

Phase 3 Example: "We've worked with many companies around the world to deliver solutions that meet their unique needs."
becomes
"We've delivered tailored solutions to 120+ companies in 14 countries."

CRITICAL REQUIREMENTS:
- Maintain the brand tonality: {brand_tonality}
- Preserve primary keyword: {primary_keyword}
- Keep all HTML formatting tags intact
- Achieve exactly {reduction_percentage}% length reduction
- Ensure content flows naturally with preceding and succeeding context

OUTPUT FORMAT:
Return the output as a JSON object with the shortened text in HTML format:

{{
    "shortened_text": "your shortened content here in HTML format",
    "original_length": original_character_count,
    "new_length": new_character_count,
    "reduction_achieved": percentage_reduced,
    "keyword_preserved": true/false
}}

IMPORTANT:
1. Return the output in HTML format within the JSON.
2. Do not give any additional comments outside the JSON.
3. Return <p> tag in the output if the output is not a heading or subheading.
4. Do not include ```html or ```json in your response.
5. Preserve the exact HTML structure and formatting of the original text.
"""
        return prompt

    @staticmethod
    def get_streaming_text_shortening_prompt(
        text_chunk: str,
        context: Dict[str, Any],
        chunk_number: int,
        total_chunks: int
    ) -> str:
        """
        Generate streaming prompt for processing text chunks in real-time
        
        Args:
            text_chunk: Current chunk of text to process
            context: Context including brand_tonality, primary_keyword, etc.
            chunk_number: Current chunk number for progress tracking
            total_chunks: Total number of chunks
            
        Returns:
            str: Formatted streaming prompt
        """
        
        brand_tonality = context.get('brand_tonality', 'professional')
        primary_keyword = context.get('primary_keyword', '')
        language = context.get('language', 'English')
        reduction_percentage = context.get('reduction_percentage', 30)
        before_context = context.get('before_context', '')
        after_context = context.get('after_context', '')
        
        prompt = f"""
STREAMING CONTENT EDITOR - Chunk {chunk_number}/{total_chunks}

You are processing chunk {chunk_number} of {total_chunks} in a streaming text shortening workflow.

INPUT CHUNK:
{text_chunk}

BEFORE CONTEXT:
{before_context}

AFTER CONTEXT:
{after_context}

CONTEXT:
- Brand Tonality: {brand_tonality}
- Primary Keyword: {primary_keyword}
- Language: {language}
Goal:
1. Reduce the length of the “Text to be edited” by 30%.
2. Preserve the primary keyword, if and wherever mentioned.
3. Keep changes to a minimum.
4. Do not add facts or figures from your end.
5. Preserve all formatting <p>, <H3>, <H2>, <H1> tags

Process:

The shortening process is a 3-phase process detailed below-

Phase 1: Structural Compression – Remove redundancy at the macro level

Phase 1, Step 1: Delete repetition: If the same idea is expressed twice in different words, keep the sharper one.
Phase 1, Step 2: Cut off-ramps: Remove tangents or subplots that don’t directly serve the main message.
Phase 1, Step 3: Merge overlapping points: Combine similar sentences into a single, high-impact one.

Phase 1 Example: "Our platform is fast, efficient, and saves time for users."
becomes
"Our platform saves time with unmatched speed and efficiency."

Phase 2: Sentence Compression – Tighten at the micro level
Phase 2, Step 1: Replace phrases with single words:
Phase 2, Step 2: Strip filler words: very, really, actually, basically, in fact.
Phase 2, Step 3: Use active voice: Cuts length and adds energy.
Phase 2, Step 4: Prune qualifiers unless essential (might, perhaps, somewhat).

Phase 2 Example: "It is important to note that this feature will help users."
becomes
"This feature helps users."




Phase 3: Impact Refinement – Keep only what earns its place
Phase 3, Step 1: Run the “So what?” test: If a word, sentence, or section doesn’t directly add value, cut it.
Phase 3, Step 2: Focus on the core promise: Readers should still get the full message even if they skim.
Phase 3, Step 3: Prioritize numbers & specifics over vague claims.

Phase 3 Example: "We’ve worked with many companies around the world to deliver solutions that meet their unique needs."
becomes
"We’ve delivered tailored solutions to 120+ companies in 14 countries."

OUTPUT:
Return only the shortened chunk in JSON format:

{{
    "chunk_number": {chunk_number},
    "shortened_chunk": "shortened HTML content here",
    "chunk_reduction": percentage_reduced_for_this_chunk,
    "keyword_found": true/false,
    "processing_notes": "brief note about changes made"
}}

Process this chunk efficiently while maintaining quality and consistency.
"""
        return prompt

    @staticmethod
    def get_content_analysis_prompt(
        full_text: str,
        brand_tonality: str,
        primary_keyword: str
    ) -> str:
        """
        Generate prompt for analyzing content before shortening
        
        Args:
            full_text: Complete text to analyze
            brand_tonality: Brand voice guidelines
            primary_keyword: SEO keyword to track
            
        Returns:
            str: Analysis prompt for content preparation
        """
        
        prompt = f"""
CONTENT ANALYSIS FOR SHORTENING PREPARATION

Analyze the following content to prepare for optimal shortening:

CONTENT TO ANALYZE:
{full_text}

ANALYSIS CONTEXT:
- Brand Tonality: {brand_tonality}
- Primary Keyword: {primary_keyword}

ANALYSIS REQUIREMENTS:

1. **Content Structure Analysis:**
   - Identify main sections and subsections
   - Map heading hierarchy (H1, H2, H3, etc.)
   - Count paragraphs and their purposes

2. **Redundancy Detection:**
   - Find repeated concepts or ideas
   - Identify overlapping sentences
   - Spot unnecessary elaborations

3. **Keyword Analysis:**
   - Locate all instances of primary keyword: "{primary_keyword}"
   - Identify keyword-rich sentences that must be preserved
   - Find keyword variations and synonyms

4. **Content Priority Mapping:**
   - Rank paragraphs by importance (1-5 scale)
   - Identify core messages vs supporting details
   - Find sentences that can be merged or eliminated

5. **Shortening Strategy:**
   - Recommend specific areas for reduction
   - Suggest sentence combinations
   - Identify safe-to-remove content

OUTPUT FORMAT:
Return analysis as JSON:

{{
    "content_stats": {{
        "total_characters": number,
        "total_words": number,
        "paragraph_count": number,
        "heading_count": number
    }},
    "keyword_analysis": {{
        "keyword_frequency": number,
        "keyword_locations": ["paragraph numbers"],
        "critical_keyword_sentences": ["sentences containing keyword"]
    }},
    "shortening_recommendations": {{
        "high_priority_sections": ["sections to preserve"],
        "redundant_content": ["areas to reduce"],
        "merge_opportunities": ["sentences that can be combined"],
        "estimated_reduction_potential": percentage
    }},
    "structure_preservation": {{
        "critical_headings": ["headings to preserve"],
        "formatting_elements": ["HTML tags found"],
        "content_flow": "assessment of logical flow"
    }}
}}
"""
        return prompt
