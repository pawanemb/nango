"""
Brand Tonality Mapping Configuration
Maps tonality values to specific tone descriptions for dynamic content generation
"""

BRAND_TONALITY_MAPPING = {
    "formality": {
        "ceremonial": {
            "instruction": "Use highly structured, protocol-driven language with formal protocols and ceremonial respect. Maintain institutional dignity and follow traditional communication patterns.",
            "modifiers": {
                "transitions": ["Furthermore", "In accordance with", "As befitting", "Pursuant to", "In the spirit of", "With due deference to"],
                "punctuation": "formal",
                "sentenceStructure": "complex, subordinate clauses",
                "vocabulary": "elevated, institutional",
                "examples": "historical precedents, formal citations"
            },
            "sentenceLength": "long, elaborate",
            "contractions": 0.0,
            "personalPronouns": 0.1
        },
        "formal": {
            "instruction": "Write professionally with precise, objective language. Use complete sentences, avoid contractions, and maintain business-appropriate tone throughout.",
            "modifiers": {
                "transitions": ["Therefore", "However", "Subsequently", "Moreover", "Consequently", "In addition"],
                "punctuation": "standard, minimal emphasis",
                "sentenceStructure": "complete, well-formed",
                "vocabulary": "professional, precise",
                "examples": "industry standards, documented cases"
            },
            "sentenceLength": "medium to long",
            "contractions": 0.1,
            "personalPronouns": 0.3
        },
        "neutral": {
            "instruction": "Use clear, balanced language that is neither too formal nor casual. Focus on clarity and conciseness while remaining accessible.",
            "modifiers": {
                "transitions": ["Next", "Also", "Then", "Additionally", "Similarly", "On the other hand"],
                "punctuation": "balanced",
                "sentenceStructure": "clear, varied",
                "vocabulary": "standard, accessible",
                "examples": "common scenarios, relatable situations"
            },
            "sentenceLength": "medium",
            "contractions": 0.4,
            "personalPronouns": 0.5
        },
        "conversational": {
            "instruction": "Write like you're talking to a friend or colleague. Use contractions naturally, ask engaging questions, and include personal touches.",
            "modifiers": {
                "transitions": ["So", "And", "But", "Plus", "Actually", "By the way"],
                "punctuation": "casual, some emphasis",
                "sentenceStructure": "varied, some fragments OK",
                "vocabulary": "everyday, approachable",
                "examples": "personal stories, everyday situations"
            },
            "sentenceLength": "varied, natural",
            "contractions": 0.8,
            "personalPronouns": 0.8
        },
        "colloquial": {
            "instruction": "Use everyday language, idioms, and relatable expressions. Don't be afraid of slang when appropriate, and embrace casual communication patterns.",
            "modifiers": {
                "transitions": ["Anyway", "So like", "Oh, and", "BTW", "Real talk", "No joke"],
                "punctuation": "casual, lots of emphasis",
                "sentenceStructure": "fragments common, natural flow",
                "vocabulary": "slang-friendly, current",
                "examples": "pop culture, street-smart scenarios"
            },
            "sentenceLength": "short, punchy",
            "contractions": 0.9,
            "personalPronouns": 0.9
        }
    },
    
    "attitude": {
        "reverent": {
            "instruction": "Show deep respect for the subject matter and audience. Use deferential language, acknowledge expertise humbly, and approach topics with appropriate gravity.",
            "modifiers": {
                "qualifiers": ["humbly", "respectfully", "with great care", "thoughtfully"],
                "acknowledgments": ["As experts have noted", "Distinguished authorities suggest", "Learned scholars indicate"],
                "tone": "deferential, respectful",
                "perspective": "humble observer",
                "vocabulary": "respectful, measured",
                "examples": "authoritative sources, established wisdom"
            },
            "confidence": 0.3,
            "assertiveness": 0.2
        },
        "respectful": {
            "instruction": "Maintain politeness and courtesy throughout. Acknowledge different viewpoints gracefully and show consideration for diverse perspectives.",
            "modifiers": {
                "qualifiers": ["perhaps", "it seems", "one might consider", "it appears"],
                "acknowledgments": ["Others may feel", "Different perspectives exist", "Various viewpoints suggest"],
                "tone": "polite, considerate",
                "perspective": "thoughtful contributor",
                "vocabulary": "courteous, inclusive",
                "examples": "balanced viewpoints, diverse perspectives"
            },
            "confidence": 0.5,
            "assertiveness": 0.4
        },
        "direct": {
            "instruction": "Be straightforward and honest. Cut through unnecessary fluff and get to the point without sugar-coating or excessive politeness.",
            "modifiers": {
                "qualifiers": ["clearly", "simply", "plainly", "directly"],
                "acknowledgments": ["The facts show", "Evidence indicates", "Results demonstrate"],
                "tone": "straightforward, honest",
                "perspective": "clear communicator",
                "vocabulary": "precise, unambiguous",
                "examples": "concrete facts, clear outcomes"
            },
            "confidence": 0.8,
            "assertiveness": 0.7
        },
        "witty": {
            "instruction": "Include clever observations, wordplay, and light humor. Make smart connections that will surprise and delight readers with unexpected insights.",
            "modifiers": {
                "qualifiers": ["cleverly", "surprisingly", "unexpectedly", "amusingly"],
                "acknowledgments": ["As the saying goes", "Funny thing is", "Plot twist", "Here's the kicker"],
                "tone": "playful, intelligent",
                "perspective": "clever observer",
                "vocabulary": "creative, unexpected",
                "examples": "amusing analogies, clever comparisons"
            },
            "confidence": 0.7,
            "assertiveness": 0.6,
            "humor": 0.8
        },
        "bold": {
            "instruction": "Take confident positions without apology. Use assertive language, strong declarative statements, and don't hesitate to challenge conventional thinking.",
            "modifiers": {
                "qualifiers": ["definitively", "absolutely", "undoubtedly", "without question"],
                "acknowledgments": ["The reality is", "Make no mistake", "Here's what's actually happening"],
                "tone": "confident, assertive",
                "perspective": "authoritative voice",
                "vocabulary": "strong, definitive",
                "examples": "bold moves, game-changing decisions"
            },
            "confidence": 0.95,
            "assertiveness": 0.9
        }
    },

    "energy": {
        "serene": {
            "instruction": "Keep language calm and composed. Use measured pacing, peaceful imagery when appropriate, and maintain a tranquil, steady rhythm.",
            "modifiers": {
                "pacing": "slow, measured",
                "imagery": ["gentle", "flowing", "peaceful", "calm"],
                "rhythm": "steady, unhurried",
                "vocabulary": "soothing, composed",
                "transitions": ["Gently", "Quietly", "Softly", "Peacefully"],
                "examples": "meditative practices, nature imagery"
            },
            "exclamationPoints": 0.1,
            "capsLock": 0.0,
            "energyWords": 0.2
        },
        "grounded": {
            "instruction": "Write with thoughtful, steady energy. Be reliable and consistent, focusing on substance and practical wisdom rather than flashy excitement.",
            "modifiers": {
                "pacing": "steady, reliable",
                "imagery": ["solid", "rooted", "stable", "dependable"],
                "rhythm": "consistent, measured",
                "vocabulary": "substantial, practical",
                "transitions": ["Steadily", "Consistently", "Reliably", "Methodically"],
                "examples": "time-tested approaches, proven methods"
            },
            "exclamationPoints": 0.2,
            "capsLock": 0.0,
            "energyWords": 0.4
        },
        "upbeat": {
            "instruction": "Maintain energetic, positive language throughout. Use active voice, dynamic verbs, and create a sense of momentum and optimism.",
            "modifiers": {
                "pacing": "lively, dynamic",
                "imagery": ["bright", "vibrant", "energetic", "dynamic"],
                "rhythm": "bouncy, engaging",
                "vocabulary": "positive, action-oriented",
                "transitions": ["Excitingly", "Dynamically", "Energetically", "Vibrantly"],
                "examples": "success stories, positive outcomes"
            },
            "exclamationPoints": 0.6,
            "capsLock": 0.1,
            "energyWords": 0.8
        },
        "excitable": {
            "instruction": "Show high-pitched enthusiasm and infectious energy. Use lots of exclamation points, dynamic language, and create genuine excitement about the topic.",
            "modifiers": {
                "pacing": "rapid, enthusiastic",
                "imagery": ["explosive", "electrifying", "thrilling", "incredible"],
                "rhythm": "fast, energetic",
                "vocabulary": "superlatives, intense",
                "transitions": ["OMG!", "And then!", "But wait!", "Plot twist!"],
                "examples": "viral moments, breakthrough discoveries"
            },
            "exclamationPoints": 0.9,
            "capsLock": 0.3,
            "energyWords": 0.95
        },
        "hypeDriven": {
            "instruction": "Create maximum excitement and FOMO (Fear of Missing Out). Use extreme superlatives, urgency language, and hype-beast terminology that makes everything sound like the next big thing.",
            "modifiers": {
                "pacing": "urgent, breathless",
                "imagery": ["game-changing", "revolutionary", "legendary", "iconic", "next-level"],
                "rhythm": "intense, non-stop",
                "vocabulary": "extreme superlatives, hype terminology",
                "transitions": ["BREAKING!", "URGENT!", "EXCLUSIVE!", "LIMITED TIME!"],
                "examples": "viral trends, breakthrough moments, exclusive drops"
            },
            "avoidPhrases": ["Pretty good", "Decent", "Okay", "Fine", "Average", "Normal"],
            "exclamationPoints": 0.95,
            "capsLock": 0.6,
            "energyWords": 1.0,
            "urgencyLanguage": 0.9,
            "superlatives": 0.95,
            "fomo": 0.9
        }
    },

    "clarity": {
        "technical": {
            "instruction": "Use industry-specific terminology and expert-level language. Assume reader familiarity with technical concepts and include precise, specialized vocabulary.",
            "modifiers": {
                "vocabulary": "specialized, precise",
                "terminology": "industry-specific, technical",
                "explanations": "assumes expertise",
                "examples": "technical specifications, expert scenarios",
                "structure": "logical, systematic"
            },
            "jargonLevel": 0.9,
            "explanationDepth": 0.9,
            "assumedKnowledge": 0.9
        },
        "precise": {
            "instruction": "Provide detailed but easy to follow explanations. Be accurate and thorough while maintaining readability for informed audiences.",
            "modifiers": {
                "vocabulary": "accurate, specific",
                "terminology": "well-defined, clear",
                "explanations": "detailed but accessible",
                "examples": "specific, well-chosen",
                "structure": "organized, methodical"
            },
            "jargonLevel": 0.6,
            "explanationDepth": 0.8,
            "assumedKnowledge": 0.6
        },
        "clear": {
            "instruction": "Avoid jargon and use plain language that anyone can understand. Focus on clarity and accessibility without dumbing down the content.",
            "modifiers": {
                "vocabulary": "accessible, clear",
                "terminology": "common usage, defined when needed",
                "explanations": "clear, straightforward",
                "examples": "relatable, everyday",
                "structure": "logical, easy to follow"
            },
            "jargonLevel": 0.3,
            "explanationDepth": 0.6,
            "assumedKnowledge": 0.4
        },
        "simplified": {
            "instruction": "Break down complex ideas into digestible chunks. Use short paragraphs, bullet points where helpful, and avoid any unnecessary complexity.",
            "modifiers": {
                "vocabulary": "basic, everyday",
                "terminology": "avoided or heavily explained",
                "explanations": "step-by-step, chunked",
                "examples": "very simple, relatable",
                "structure": "short sections, clear breaks"
            },
            "jargonLevel": 0.1,
            "explanationDepth": 0.4,
            "assumedKnowledge": 0.2
        },
        "abstract": {
            "instruction": "Use conceptual, metaphor-driven language that paints pictures and creates atmospheric understanding. Focus on the essence and feeling of ideas.",
            "modifiers": {
                "vocabulary": "conceptual, evocative",
                "terminology": "metaphorical, artistic",
                "explanations": "impressionistic, atmospheric",
                "examples": "metaphors, analogies, imagery",
                "structure": "flowing, artistic"
            },
            "jargonLevel": 0.2,
            "explanationDepth": 0.7,
            "assumedKnowledge": 0.5,
            "metaphorUsage": 0.9
        }
    }
}

def get_tonality_description(tonality_type: str, value: str) -> dict:
    """
    Get the description and characteristics for a specific tonality value
    
    Args:
        tonality_type: Type of tonality (formality, attitude, energy, clarity
        value: Specific value for that tonality type
        
    Returns:
        Dictionary containing description, characteristics, and example phrases
    """
    return BRAND_TONALITY_MAPPING.get(tonality_type, {}).get(value, {})

def build_tonality_prompt(brand_tonality: dict) -> str:
    """
    Build a comprehensive tonality prompt based on brand tonality settings
    
    Args:
        brand_tonality: Dictionary containing formality, attitude, energy, clarity
        
    Returns:
        Formatted prompt string for AI content generation
    """
    prompt_parts = []
    
    for tonality_type, value in brand_tonality.items():
        if value and tonality_type in BRAND_TONALITY_MAPPING:
            tonality_info = get_tonality_description(tonality_type, value)
            if tonality_info:
                # Include the complete raw data structure for this tonality
                import json
                raw_data = json.dumps(tonality_info, indent=2)
                
                prompt_part = f"""
**{tonality_type.title()} Instruction**: "{value}": {raw_data}
"""
                prompt_parts.append(prompt_part)
    
    if prompt_parts:
        return f"""
## Brand Tonality Guidelines:
Please ensure the content follows these specific tonality requirements. Use the complete data structure provided for each tonality dimension:

{''.join(prompt_parts)}

Apply these tonality guidelines consistently throughout the entire blog content. Use all the modifiers, numerical parameters, and specific instructions provided in the data structure above.
"""
    
    return ""

def validate_brand_tonality(brand_tonality: dict) -> dict:
    """
    Validate and normalize brand tonality values
    
    Args:
        brand_tonality: Dictionary containing tonality values
        
    Returns:
        Validated and normalized tonality dictionary
    """
    validated = {}
    
    for tonality_type, value in brand_tonality.items():
        if tonality_type in BRAND_TONALITY_MAPPING and value:
            # Normalize value (lowercase, replace spaces with underscores)
            normalized_value = str(value).lower().replace(' ', '_').replace('-', '_')
            
            # Check if normalized value exists in mapping
            if normalized_value in BRAND_TONALITY_MAPPING[tonality_type]:
                validated[tonality_type] = normalized_value
            else:
                # Try to find closest match or use default
                available_values = list(BRAND_TONALITY_MAPPING[tonality_type].keys())
                if available_values:
                    validated[tonality_type] = available_values[0]  # Use first available as default
    
    return validated
