"""
Integration code for internal linking research in blog generation task
Add this code to generate_final_blog_step function BEFORE Claude prompt construction
"""

# ADD THIS IMPORT at the top of blog_generation.py
from app.services.internal_linking_research_service import (
    generate_internal_linking_research, 
    format_internal_links_for_claude,
    InternalLinkingResearchService
)

def integrate_internal_linking_research(blog_request, project, blog_id, redis_key, usage_tracker):
    """
    Integration function to add internal linking research to blog generation
    Add this function call BEFORE Claude prompt construction in generate_final_blog_step
    
    Args:
        blog_request: Blog generation request payload
        project: Project information dict
        blog_id: Blog document ID
        redis_key: Redis key for task tracking
        usage_tracker: Usage tracking dict
        
    Returns:
        tuple: (internal_links_data, updated_usage_tracker)
    """
    try:
        # Update progress to show research phase
        safe_update_progress(blog_id, 10, redis_key, "researching_internal_links")
        logger.info(f"🔍 Starting internal linking research for blog_id: {blog_id}")
        
        # Generate internal linking research
        internal_urls = generate_internal_linking_research(blog_request, project)
        
        # Update progress after research
        safe_update_progress(blog_id, 25, redis_key, "research_completed")
        
        # Format URLs for Claude prompt
        if internal_urls:
            internal_links_data = format_internal_links_for_claude(internal_urls)
            logger.info(f"🔗 Prepared {len(internal_urls)} internal URLs for Claude")
        else:
            internal_links_data = "No internal linking opportunities found."
            logger.warning("🔗 No internal URLs found for linking")
        
        # Update usage tracker
        service = InternalLinkingResearchService()
        updated_usage_tracker = service.update_usage_tracker(
            usage_tracker, 
            queries_count=5, 
            searches_count=5
        )
        
        return internal_links_data, updated_usage_tracker
        
    except Exception as e:
        logger.error(f"Internal linking research failed: {str(e)}")
        # Don't fail the blog generation, just skip internal linking
        return "Internal linking research unavailable.", usage_tracker


# ====================================================================
# EXACT CODE TO ADD TO generate_final_blog_step FUNCTION
# Add this code around line 425 BEFORE Claude prompt construction
# ====================================================================

def add_to_blog_generation_task():
    """
    This is the exact code to add to generate_final_blog_step function
    Place this AFTER line 425 (after Redis status update) and BEFORE Claude prompt construction
    """
    
    # 🔗 INTERNAL LINKING RESEARCH - Add this code block
    logger.info(f"🔍 Starting internal linking research phase for blog_id: {blog_id}")
    
    # Check if internal linking is enabled for this project
    internal_linking_enabled = project.get("internal_linking_enabled", True)
    
    if internal_linking_enabled:
        # Import the research service
        from app.services.internal_linking_research_service import (
            generate_internal_linking_research, 
            format_internal_links_for_claude,
            InternalLinkingResearchService
        )
        
        # Update progress to show research phase
        safe_update_progress(blog_id, 10, redis_key, "researching_internal_links")
        
        # Generate internal linking research
        internal_urls = generate_internal_linking_research(blog_request, project)
        
        # Update progress after research
        safe_update_progress(blog_id, 25, redis_key, "research_completed")
        
        # Format URLs for Claude prompt
        if internal_urls:
            internal_links_data = format_internal_links_for_claude(internal_urls)
            logger.info(f"🔗 Prepared {len(internal_urls)} internal URLs for Claude")
        else:
            internal_links_data = "No internal linking opportunities found."
            logger.warning("🔗 No internal URLs found for linking")
        
        # Update usage tracker with research calls
        try:
            service = InternalLinkingResearchService()
            usage_tracker = service.update_usage_tracker(
                usage_tracker, 
                queries_count=5, 
                searches_count=5
            )
        except Exception as tracker_error:
            logger.warning(f"Failed to update usage tracker for research: {str(tracker_error)}")
    else:
        internal_links_data = "Internal linking disabled for this project."
        logger.info("🔗 Internal linking disabled for this project, skipping research")
        safe_update_progress(blog_id, 25, redis_key, "research_skipped")


# ====================================================================
# CLAUDE PROMPT MODIFICATION
# Modify the existing blog_prompt around line 512 to include internal links
# ====================================================================

def modify_claude_prompt():
    """
    This shows how to modify the existing Claude prompt to include internal links
    Find the line with <scraped_information> and add the internal links section after it
    """
    
    # FIND THIS SECTION in the existing prompt (around line 512):
    # xii. This is the scraped research data for some of the sub-headings of the blog.  
    # Make sure to process the sub-heading research information for their respective scraped data.  
    # Here is the scraped data: <scraped_information>{raw_sources}</scraped_information>  
    
    # MODIFY IT TO THIS:
    blog_prompt_addition = f"""
xii. This is the scraped research data for some of the sub-headings of the blog.  
Make sure to process the sub-heading research information for their respective scraped data.  
Here is the scraped data: <scraped_information>{raw_sources}</scraped_information>  

xiii. INTERNAL LINKING OPPORTUNITIES - Use these URLs from the same website for natural internal linking:
<internal_links>
{internal_links_data}
</internal_links>
"""

    # ALSO UPDATE THE OUTPUT INSTRUCTIONS section to include internal linking:
    output_instructions_addition = """
– **INTERNAL LINKING: Select 3-5 relevant URLs from <internal_links> and naturally integrate them as anchor links within the content. Format as: <a href="URL">descriptive anchor text</a>. Only use URLs that are genuinely relevant to the content being discussed.**
"""


# ====================================================================
# COMPLETE INTEGRATION EXAMPLE
# This shows the exact code structure for the integration
# ====================================================================

def complete_integration_example():
    """
    This is the complete integration showing where to place the code
    in the generate_final_blog_step function
    """
    
    # ... existing code until line 425 ...
    
    # Update Redis status - Step 2 processing started (45% total: 25% + 20%)
    redis_key = f"blog_generation_task:{blog_id}"
    try:
        task_data = redis_client.get(redis_key)
        if task_data:
            task_info = json.loads(task_data)
            task_info["steps"]["blog_generation"]["status"] = "processing"
            task_info["steps"]["blog_generation"]["progress"] = 5
            redis_client.set(redis_key, json.dumps(task_info), ex=86400)
    except Exception as redis_error:
        logger.warning(f"Failed to update Redis status: {str(redis_error)}")
    
    # 🔗 ADD THIS ENTIRE BLOCK HERE - Internal Linking Research
    logger.info(f"🔍 Starting internal linking research phase for blog_id: {blog_id}")
    
    # Check if internal linking is enabled for this project
    internal_linking_enabled = project.get("internal_linking_enabled", True)
    
    if internal_linking_enabled:
        try:
            # Import the research service
            from app.services.internal_linking_research_service import (
                generate_internal_linking_research, 
                format_internal_links_for_claude,
                InternalLinkingResearchService
            )
            
            # Update progress to show research phase
            safe_update_progress(blog_id, 10, redis_key, "researching_internal_links")
            
            # Generate internal linking research
            internal_urls = generate_internal_linking_research(blog_request, project)
            
            # Update progress after research
            safe_update_progress(blog_id, 25, redis_key, "research_completed")
            
            # Format URLs for Claude prompt
            if internal_urls:
                internal_links_data = format_internal_links_for_claude(internal_urls)
                logger.info(f"🔗 Prepared {len(internal_urls)} internal URLs for Claude")
            else:
                internal_links_data = "No internal linking opportunities found."
                logger.warning("🔗 No internal URLs found for linking")
            
            # Update usage tracker with research calls
            try:
                service = InternalLinkingResearchService()
                usage_tracker = service.update_usage_tracker(
                    usage_tracker, 
                    queries_count=5, 
                    searches_count=5
                )
            except Exception as tracker_error:
                logger.warning(f"Failed to update usage tracker for research: {str(tracker_error)}")
                
        except Exception as research_error:
            logger.error(f"Internal linking research failed: {str(research_error)}")
            internal_links_data = "Internal linking research unavailable."
    else:
        internal_links_data = "Internal linking disabled for this project."
        logger.info("🔗 Internal linking disabled for this project, skipping research")
        safe_update_progress(blog_id, 25, redis_key, "research_skipped")
    
    # ... continue with existing code (Extract raw brand tonality, etc.) ...
    
    # Extract raw brand tonality (no dynamic transformation)
    brand_tonality = blog_request.get("brand_tonality", {})
    # ... rest of existing code until prompt construction ...
    
    # MODIFY the existing blog_prompt construction to include internal links
    # Find the line around 512 and update it like this:
    
    blog_prompt = f"""
    
A. Tone, voice and humanisation - high priority
1. Human voice first: write like an expert explaining something to a smart peer. Avoid corporate filler and familiar AI clichés.
2. Use natural transitions, rhetorical questions sparingly, vivid verbs, precise nouns, and one or two short illustrative examples.
3. Use sentence variation and occasional parenthetical asides to break purely declarative patterns.
4. Match the requested style axes supplied in the input:
{raw_tonality_json}
Use these to set voice choices such as contractions, rhetorical devices, and sentence complexity.
5. Adopt a "Smart Colleague" Mental Model: Imagine you are writing this for an intelligent colleague in a different department. You don't need to over-explain basic concepts, but you do need to make your specialized knowledge clear and compelling. The tone should be helpful and confident. Use parenthetical asides (like this one) to add a bit of personality or clarify a minor point.

# ... existing prompt content ...

xi. <outline>{raw_outline}</outline>  
xii. This is the scraped research data for some of the sub-headings of the blog.  
Make sure to process the sub-heading research information for their respective scraped data.  
Here is the scraped data: <scraped_information>{raw_sources}</scraped_information>  

xiii. INTERNAL LINKING OPPORTUNITIES - Use these URLs from the same website for natural internal linking:
<internal_links>
{internal_links_data}
</internal_links>

D.
### Output Instructions:
– Write a complete, well-structured blog article in the language specified by <language_preference>.  
– Follow the given <outline> but enrich and rearrange naturally if it improves flow.  
– Integrate <primary_keyword> and <secondary_keyword> organically into headings and body copy without keyword stuffing.  
– Use the <scraped_information> under its relevant sub-heading, paraphrasing and expanding it into fluent paragraphs.  
– **INTERNAL LINKING: Select 3-5 relevant URLs from <internal_links> and naturally integrate them as anchor links within the content. Format as: <a href="URL">descriptive anchor text</a>. Only use URLs that are genuinely relevant to the content being discussed.**
– Aim for the approximate <word_count> but allow a ±10% variation for natural writing.  

# ... rest of existing prompt ...
"""