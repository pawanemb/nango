"""
Sources Collection Prompts for Enhanced Outline Customization Service
Separate prompt management for better code organization and maintainability
"""

from typing import Dict, Any, Optional, List


class SourcesCollectionPrompts:
    """Centralized prompt management for sources collection and processing"""

    @staticmethod
    def get_combined_sources_knowledge_extraction_prompt(
        blog_title: str,
        heading_title: str,
        subsection_title: str,
        combined_sources: List[Dict[str, str]],
        outline_json: str = None
    ) -> str:
        """
        Generate prompt for extracting knowledge from multiple combined sources
        
        Args:
            blog_title: The main blog title for context
            heading_title: The heading title for context
            subsection_title: The specific subsection being processed
            combined_sources: List of dicts with 'url', 'title', 'content' keys
            outline_json: The full blog outline structure for context
            
        Returns:
            str: Formatted prompt string for OpenAI processing of combined sources
        """
        # Build the sources content section
        sources_content = ""
        for i, source in enumerate(combined_sources, 1):
            sources_content += f"""
SOURCE {i}: {source['url']} - {source['title']}
CONTENT:
{source['content'][:1500]}  

"""

        # Add outline context if provided
        outline_context = ""
        if outline_json:
            outline_context = f"""
Blog Outline Structure:
{outline_json}

"""

        prompt = f"""
Input: 
 H3 where this info will be used: {subsection_title}
Outline:{outline_context}

Sources data: {sources_content}

"""
        return prompt

    @staticmethod
    def get_knowledge_extraction_prompt(
        blog_title: str,
        heading_title: str,
        subsection_title: str,
        content_preview: str,
        url: str
    ) -> str:
        """
        Generate prompt for extracting knowledge and citations from scraped content
        
        Args:
            blog_title: The main blog title for context
            heading_title: The heading title for context
            subsection_title: The specific subsection being processed
            content_preview: The scraped content to process
            url: The source URL
            
        Returns:
            str: Formatted prompt string for OpenAI processing
        """
        prompt = f"""Role
You are a researcher who is able to retrieve information from webpages for your content writers.

Input: 
Blog Title: {blog_title}
Main Heading: {heading_title}
Sub-heading: {subsection_title}
Scraped page content (in RAW HTML format): {content_preview}

Goals:

Extract the full blog content word by word: Extract the blog content from the scraped blog page without making any changes to the content and formatting.
Understand the relevance of the content with the sub-heading: Evaluate the blog information to understand its relevance with the sub-heading. 
Process information only if relevant: You must process this task only if you find that the scraped information passed in the input is directly or partially related to the sub-heading. The output of this response will be processed in the blog generation process of writing the sub-heading mentioned in the input for the mentioned heading and blog title. Give your response as: 'Information not found' in the response if it is irrelevant. 
Extract important information: The criteria for doing this must be following:
a. The information must satisfy the information need of the sub-heading.
b. It must be trustworthy.
c. It must not be generic and too obvious.
Classify the gathered information: On the basis of the gathered information, classify the information in any of the two categories: Citation Information, and Understanding Information. 
a) Citation Information: This will only include statistics and facts (majorly number-driven) which can be quoted verbatim along with the source link to support any information and improve its authority. These must be very specific and to the point and must not contain any generic information. In doing this, you must ensure that all the citation informations are logical and have a coherent meaning. 
b) Understanding Information: This is a non-generic piece of information which will add depth to the blog over and above the obvious information to give any argument, establish a hypothesis or explain any concept. This will include the information pieces which are not citation information. 

Process:

Step 1, Read the markdown text received to you word by word.
Step 2, Extract the blog content in the text format. 
Step 3, Don't omit any blog text.
Step 4, Ignore all the images and non-blog parts mentioned in the content.
Step 5, Read the entire blog content thoroughly.
Step 6. Evaluate if the information is directly or partially relevant to the sub-heading. Do not exclude content just because it's brief or not detailed.
Step 7. If there is zero relevance whatsoever, return the output as: 'Information not found'. 
Step 8. If there is any partial or supporting relevance, segregate it into Citation and Understanding Information.
Step 9, For citation information, keep the wording of the information intact, without making any character, letter, word or sentence changes from the text in the original source.
Step 10, Don't give the website link of the source website in your any response. This is critical for the success of the task.  

Output:
Give output as JSON values in the following format: {{"Citation Information": ["Information 1", "Information 2", "Information n"], "Understanding Information": ["Information 1", "Information 2", "Information n"]}}.
Give the response as 'Information not found' where the information is irrelevant.
Give only the Citation and Understanding Information in your response if the information is relevant. 
Do not add any content from your side.
Do not make any additional comment from your side.
Do not acknowledge the completion of the task.
Give only the content part and ignore other sections. 
Do not include ```json in your response. 
Do not stop processing until all the content mentioned in the scraped page is covered in the response.
Do not give citations and understanding information for the sake of it. In cases where there is no citation or understanding information, give 'Nil' as output. 
Do not give anchor text links of the scraped page in the final output. 
Mention the page link of the website and its name in the response before the information. 

Website: {url}
"""
        return prompt

    @staticmethod
    def get_system_message() -> str:
        """
        Get the system message for OpenAI chat completion
        
        Returns:
            str: System message for OpenAI
        """
        return "You are an expert content researcher. Extract relevant information from web content and classify it as Citation Information (statistics, facts, data) or Understanding Information (insights, explanations, concepts). Return responses in valid JSON format only."

    @staticmethod
    def get_document_processing_prompt(
        filename: str,
        subsection_title: str,
        extracted_text: str
    ) -> str:
        """
        Generate prompt for processing uploaded documents
        
        Args:
            filename: Name of the uploaded document
            subsection_title: The subsection this document is being added to
            extracted_text: Extracted text content from the document
            
        Returns:
            str: Formatted prompt for document processing
        """
        prompt = f"""Role
You are a research assistant helping to extract valuable information from uploaded documents.

Input:
Document Name: {filename}
Target Subsection: {subsection_title}
Extracted Document Content: {extracted_text}

Goals:
Analyze the document content and extract information relevant to the target subsection.
Classify information into Citation Information (facts, statistics, data) and Understanding Information (insights, explanations, concepts).
Ensure all extracted information directly relates to the subsection topic.

Process:
Step 1: Read through the entire document content carefully.
Step 2: Identify information that directly relates to the target subsection.
Step 3: Classify relevant information into two categories:
   - Citation Information: Statistics, facts, data points, research findings
   - Understanding Information: Explanations, insights, methodologies, concepts
Step 4: Ensure all information is accurate and maintains original context.
Step 5: Exclude generic or irrelevant information.

Output:
Provide response in this exact JSON format:
{{"Citation Information": ["Fact 1", "Statistic 2", "Data point 3"], "Understanding Information": ["Insight 1", "Concept 2", "Explanation 3"]}}

If no relevant information is found, respond with: "Information not found"
Do not include ```json in your response.
Do not add commentary or acknowledgments.
"""
        return prompt

    @staticmethod
    def get_custom_text_processing_prompt(
        title: str,
        subsection_title: str,
        content: str
    ) -> str:
        """
        Generate prompt for processing custom text sources
        
        Args:
            title: Title/name of the custom source
            subsection_title: Target subsection
            content: Custom text content
            
        Returns:
            str: Formatted prompt for custom text processing
        """
        prompt = f"""Role
You are a content analyst helping to process custom text sources for blog content.

Input:
Source Title: {title}
Target Subsection: {subsection_title}
Custom Content: {content}

Goals:
Extract and classify relevant information from the custom text that relates to the target subsection.
Organize information into Citation Information and Understanding Information categories.
Maintain accuracy and context of the original content.

Process:
Step 1: Analyze the custom content thoroughly.
Step 2: Identify information relevant to the target subsection.
Step 3: Separate factual data (Citation) from explanatory content (Understanding).
Step 4: Ensure information quality and relevance.
Step 5: Exclude redundant or generic information.

Output:
Return response in this JSON format only:
{{"Citation Information": ["Data point 1", "Fact 2"], "Understanding Information": ["Concept 1", "Insight 2"]}}

If content is not relevant to the subsection, respond: "Information not found"
Do not include ```json markers in response.
"""
        return prompt