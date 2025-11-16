from typing import Dict, List, Optional,Union, Any
from datetime import datetime
import logging
logger = logging.getLogger(__name__)
def format_search_results(results: Optional[List[Dict]] = None) -> str:
    """Format search results into a structured string."""
    if not results or len(results) == 0:
        return 'No research data available.'
    
    formatted_results = ["Research Findings:"]
    for i, result in enumerate(results, 1):
        formatted_result = f"""
{i}. From {result.get('source', 'Unknown Source')}:
   Title: {result.get('title', 'No Title')}
   Key Finding: "{result.get('content', 'No Content')}"
   Source URL: {result.get('source', 'No URL')}"""
        
        if date_published := result.get('datePublished'):
            try:
                formatted_date = datetime.fromisoformat(date_published).strftime('%Y-%m-%d')
                formatted_result += f"\n   Published: {formatted_date}"
            except (ValueError, TypeError):
                pass
                
        formatted_results.append(formatted_result)
    
    formatted_results.append("\nUse these findings in your introduction and cite them appropriately using [Source Name] format.")
    return "\n".join(formatted_results)

def format_outline(outline: Optional[Dict] = None) -> str:
    """Format article outline into a structured string."""
    if not outline:
        return ''
    
    sections = "\n".join(f"- {section.get('heading', '')}" for section in outline.get('sections', []))
    
    return f"""Sections:
{sections}

Conclusion: {outline.get('conclusion', '')}

FAQs: {len(outline.get('faqs', []))} questions"""

def get_introduction_prompt(
    blog_request: Dict,
    search_results: Any = None,
    # search_results: List[Dict[str, Any]] = None,
    project: Dict = None
) -> Dict[str, str]:
    """
    Generate system and user prompts for article introduction using Claude API.
    
    Args:
        blog_request: Dictionary containing blog request details
        search_results: Optional list of search results
        
    Returns:
        Dict with 'system' and 'user' prompts
    """
    primary_keyword = blog_request.get('primary_keyword')
    secondary_keywords = ', '.join(blog_request.get('secondary_keywords', []))
    keyword_intent = blog_request.get('keyword_intent')
    target_audience_age_group = ', '.join(project.get('age_groups', [])) if project and project.get('age_groups') else 'general audience'
    industry = blog_request.get('industry')
    title = blog_request.get('blog_title')
    word_count = blog_request.get('word_count')
    outline = blog_request.get('outline')
    locations = ', '.join(project.get('locations', [])) if project and project.get('locations') else 'India'
    gender = project.get('gender', "All") if project and project.get('gender') else 'All'    
    logger.info("--------------------------------------------------------")
    logger.info("--------------------------------------------------------")
    logger.info(f"Primary Keyword: {primary_keyword}")
    logger.info(f"Secondary Keywords: {secondary_keywords}")
    logger.info(f"Keyword Intent: {keyword_intent}")
    logger.info(f"Target Audience: {target_audience_age_group}")
    # logger.info(f"Industry: {industry}")
    logger.info(f"Title: {title}")
    logger.info(f"Word Count: {word_count}")
    logger.info(f"Outline: {outline}")
    import re
    # search_results = '"' + re.sub(r'\\.|[{}[\],\'"]', '', search_results).replace('\\n', ' ').strip() + '"'
    if search_results:
        if isinstance(search_results, list):
            # Join list items with a space and clean the result
            search_results_str = ' '.join(search_results)
            # Remove escape sequences and special characters
            search_results = re.sub(r'\\n|\\"|\\\'|\{|\}|\[|\]|\\\\', ' ', search_results_str).strip()
            # Remove excessive spaces
            search_results = re.sub(r'\s+', ' ', search_results)
    logger.info(f"Search Results: {search_results}")
    logger.info("--------------------------------------------------------")
    logger.info("--------------------------------------------------------")

    system_prompt = f'''
You are a highly experienced SEO content writer who is well versed in writing engaging SEO friendly blogs. You need to produce a high quality content for the introduction which is a part of the larger outline of the blog.Furthermore, you must give your response strictly in the markdown format and follow the goals and process mentioned below.
'''

    user_prompt = f"""
Input
Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords}
Intent: {keyword_intent}
Target Age Group: {target_audience_age_group}
Target Keyword Location: {locations}
Target Gender: {gender}
Title: {title}
Blog Word Count: {word_count}
Outline: {outline}
Scraped data: {search_results}

Goals 
Audience-focused: You need to first understand the audience and create content that matches their interest and need for reading the blog. By understanding the audience, you will know about the persona. Also, you will have a better context about the ideas and level of explanations to give in the introduction. Writing for a persona in mind makes the blog more engaging and chatty. A good blog introduction always puts its user on the focus and resonates with them on a personal level.  This will ensure that you don’t include abstract, vague, and ambiguous elements in your writing. 


Immediate Answer to User Query: The introduction must start by directly addressing the user’s question or the topic the blog covers. No vague or generic introductions. 


Maintain Factual Accuracy: You must ensure that all the pieces of information mentioned in the introduction are accurate and updated. Do not include any information that cannot be verified through a trustable source. This has to be especially important for the examples and case studies you include in the content.


Inclusion of primary keyword: Understand the primary keyword and include it naturally within the primary keyword. The role of the primary keyword inclusion is to ensure that the content is written to satisfy the search needs of the user. By including the primary keyword naturally you would be able to understand the context and ensure writing relevant content aligned with the reader's need. Try to include the primary keyword in the first 30 words of the introduction. 


Use simplified language: The tonality of the introduction must be direct and must avoid unnecessary complex wordings. Replace complex phrases with simpler alternatives to improve relatability. Here are a few examples of that: In order to → To; Despite the fact that → Although; Leverage → Use; Utilize → Use, Subsequent → Next, following; Commence → Start, begin; Terminate → End, stop; Ascertain → Find out, determine; Facilitate → Help, ease, enable; Expedite → Speed up, accelerate; Implement → Carry out, apply, put in place; Disseminate → Share, spread; Mitigate → Reduce, lessen, ease; Enumerate → List, count; Comprehend → Understand, grasp; Obtain → Get; Procure → Get, acquire; Endeavor → Try, attempt; Illustrate → Show, explain; Indicate → Show, point out; Demonstrate → Show, prove; Substantial → Large, significant; Adequate → Enough, sufficient; Pertinent → Relevant, related; Consolidate → Combine, merge; Constitute → Make up, form; Rectify → Fix, correct; Optimize → Improve, make better; Articulate → Express, explain; Negate → Cancel, undo; Presume → Suppose, assume; Attain → Reach, achieve; Allocate → Give, assign; Engage in → Take part in, do; Accomplish → Complete, achieve; Contemplate → Think about, consider; Scrutinize → Examine, check; Advocate → Support, recommend; Enhance → Improve, boost; Elicit → Draw out, bring out


Build natural connection: You should be able to build a natural connection with the reader with content that looks human-written. The trait of human written content is that it is very less predictable. This gives the confidence to readers that the blog writer actually cares about them and has given a confident perspective. For example, the sentence “One must take into consideration the fact that consuming an adequate quantity of hydration on a daily basis is of utmost importance for the maintenance of optimal bodily functions.”, will be less appealing to communicate a natural idea "Drinking enough water every day is essential for staying healthy."
 
Use research data: Make use of the research data provided to you to include them in the introduction with the citation rules mentioned in the output level instructions. For this, you will find the input information of the scraped content for all the sub-headings mentioned in the section. Furthermore, there would be a bifurcation of Understanding Information and Citation Information in the scraped information data of the input. You must use Understanding Information data to make your sections better with the research data provided in it without making any citations. You must consume only the most important and relevant information from this data and not necessarily consume all the information. The purpose of this data is to provide better information and understanding of the concept to write better. On the other hand, you must use the citation information only to present facts, statistics, or research by following the citation rules and duly acknowledging the source by acknowledging its name and giving it a reference link. Doing this will ensure that it reflects authority and expertise in the domain of the blog title.
Sentence structuring: A sentence is a collection of words that contains a verb and a subject, on which it acts. They express an idea by making a statement or raising a question. The idea of the sentence is to simply say ‘who’ does ‘what’. Hence they must be clear and specific. They must be logically arranged in a paragraph to make a larger sense of the introduction.. You must intend to ‘inform’ and not impress the reader with the sentences in your content. 

Paragraph structuring: A paragraph is a collection of sentences that tells about a broader-level idea. Each paragraph is unique. They save reader’s fatigue by consuming one information after another. Breaks in paragraph gives the time to pause and reflect on the understanding covered in it. Hence the paragraphs must be logically structured to cover the ideas in introduction in a logical and easy way. 

Logically structured: The sentences in the explanation of the introduction must be logically arranged and flow naturally. Include sentences and paragraphs in order that makes the most sense. To do this, start with a sentence which makes a clear statement, follow this by explanation which establishes this clear statement, and include the concluding thoughts only where they make sense. Concluding thoughts must not give the repetitive information which has already been included.  For example - 

“Representation matters.

We hear this over and over again. And most people agree.

However, not all representation is created equal, and this is important to recognize, especially to ensure your efforts in including more people in your marketing are received positively rather than being met with frustration and skepticism.

As the number of brands embracing inclusive marketing and prioritizing visual imagery that accurately represents their target audience grows, it becomes crucial for marketers to become well-versed in how to do representation in marketing the right way.

When done right, it demonstrates to underrepresented consumers that you’re committed to them and their communities. When done right, representation in marketing makes the people you serve feel seen, supported, and like they belong with you.

Below are what consumers have shared with me in recent years about what is important for them to see in terms of representation.

But first, to make sure we’re on the same page, let’s talk about why representation in marketing is so important.”

Clear and simple explanations: Don’t find fancy and long-worded things to convey an idea. You must write to inform and not impress readers. Your each sentence must be in link with the other sentences and naturally placed. All the sentences of your introduction must be clear and simple to understand. 

Reference to the other headings to build the context: While writing the content of introduction, take the reference of all the other headings in the blog also. This will help you guide the introduction accordingly and write the content that sets an introductory tone for the overall blog post. 

Avoiding redundancy and repetition: Avoid writing redundant ideas that are not directly related to the blog title. Keep the writing crisp and focused on solving users' problems. Furthermore, don’t repeat an idea once written in the content of the introduction. In cases, where you want to reiterate any special idea, support it with a follow-up idea, example or analogies rather than simply repeating it. 

Coherence: Coherence refers to how well the ideas, sentences, and paragraphs flow. They help to build a logical understanding of one sentence and one paragraph after another. This brings meaning to the content and ensures that the readers are able to clearly understand the concept. Ensure that the sentences and the paragraphs are naturally connected with each other. You can do this by using transitional words, with the caution of not repeating any idea or causing any redundancy in the introduction. 


Process 

Step 1, Understand the target audience: Understand the target audience for the blog and understand their interests, preferences, and needs for reading the blog. This will help you keep the focus on your reader and write ideas and explanations that talk rather than simply informing. By doing this you will have better ideas about giving ideas unique to them for writing the introduction. 

Step 2, Understand the primary keyword and its intent: Understand the primary keyword and intent of the primary keyword to know about the kind of information you need to give in content. For example, if the blog is of Informational intent, then it must provide clarity, explanations, or background of the concepts. For e.g., if the blog is about “What is Digital Marketing”, then the blog sub-headings must be to explain the concepts related to it. Similarly, if it is of Navigational intent, then it must guide users to specific and targeted solutions. For eg., if the blog title is about ‘iPhone pricing’, then the user must receive the various pricing options as the user is already beyond the need for getting surface-level explanations. For Commercial intent, it must help users compare, evaluate, or make decisions. For e.g., for the blog topic "SEO vs. SEM: Which Strategy Suits Your Business?", blog sub-headings must list the advantages and disadvantages for both as the users are in the decision-making stage. For Transactional intent, the content must direct users toward action-oriented content. For e.g., "How to Optimize Your Website for SEO in 5 Steps", provides clear steps for achieving this in the sub-headings. This alignment has to be further based on the category and sub-category of the blog which are based on the user selections, and clearly tells about the kind of sub-headings the users are expecting. For e.g., in a blog titled “How to Create a Sales Plan?”, the blog is of the ‘Action-Oriented’ category and ‘How-To sub-category’. For this blog, the sub-headings must give clear actionable steps for creating the sales plan and can avoid surface-level sub-headings like What is a sales plan, Importance of Sales Plan, etc. 

Step 3, Understand the secondary keywords: Understand the secondary keywords to understand the context in which the information of the primary keyword has to be covered. For example, for the primary keyword ‘email marketing benefits’, the secondary keyword ‘automation in email marketing’, establishes the need for highlighting the benefits of email marketing and gives a special emphasis on ‘automation’, as one of the benefits of email marketing. Try to include the secondary keywords by understanding the relationship between the primary and secondary keywords. 

Step 4, Alignment with the blog title: You must factor the title of the blog to directly understand the user’s expectations from the blog. The title of the blog clearly sets the goal of what, why, and how the content should be written. The introduction should align with the title of the blog to give a natural understanding of the concept in the entire blog post to the reader. For example, for a blog titled ‘Choosing the Right Mutual Funds to Invest’, you must write an introduction aligned with the reader’s need for taking the decision. 

Step 5, Adjust the complexity level based on audience: Adjust the complexity of information based on the reading grade of the audience. For example, if the target audience for the blog for the primary keyword ‘ai trends’, is school-going kids studying, lying between the age of 12-15 years, then the expectation of the reader would be to have surface-level information about the concepts, just to get the awareness on the subject. On the other hand, if the audience is from the ‘technology industry’, falling in the age group of 25-40 years, then they are expecting very precise, accurate, and actionable information. Hence the sub-headings have to go beyond surface-level explanations in this case, assuming that the readers already are aware of it and they are looking for a credible source to expand their knowledge.

Step 6, Understand the outline of the blog: Understand the outline of the blog to know about the introduction for which you have to write. Based on this, know about the context of writing the introduction and include information and ideas based on this. By understanding the outline of the blog you will come to know about the other headings and sub-headings which are to be covered in a final blog output. Write the introduction based on this only to ensure that the introduction reflects coherence in the final blog output.
 
Step 7, Utilise the Understanding Information data from the scraped information data: Use the Understanding Information data provided in the input of scraped information as the research data to improve the understanding of the concept and gather important information about it. These are mentioned in the same order of the sub-headings or sub-sections mentioned in the outline of the blog and section. You must refer the information for every sub-heading provided to you to support your content with the understanding or information provided here for every sub-heading or subsection.  While doing this, do not acknowledge the source of information and simply use the information for a better understanding of the concept. This will improve the credibility of the section content.  However, do not take the liberty of increasing the word count for the section and strictly stick to the word count. Process only highly relevant information and useful information which build natural connection within the ideas of the sentences. Do not include information from the Understanding Information data for the sake of it. 

Step 8, Utilise the Citation Information data from the scraped information data: Use the information mentioned in the Citation Information data provided in the input of the scraped information as the research data containing statistics, facts, or research that should be used and cited with the source. This will improve the authority of the section content as it would entail research data that will improve the understanding of the concept. These are mentioned in the same order of the sub-headings or sub-sections mentioned in the outline of the blog and section. You must refer the information for every sub-heading provided to you to support your content with information of statistics, fact, or research data. Make sure to acknowledge the source of the information for this and follow the citation rule to reference it with the citation link. However, do not take the liberty of increasing the word count for the section and strictly stick to the word count. Process only highly relevant information and useful information which build natural connection within the ideas of the sentences. Do not include information from the Understanding Information data for the sake of it.

Step 9, Alignment with the word count: Adhere to the word count based on the total word count mentioned in the input for the entire blog based on this:


Total 2500 words: Introduction of 125-175 words 
Total 1500 words: Introduction of 100-150 words
Total 1000 words: Introduction of up to 100 words

Step 10, Do not include subjective ideas: Do not include any subjective ideas from your end. All the sentences for writing the introduction must be logical and factually accurate. Don’t express your personal beliefs and take the support of facts and research only to establish a point. For example, you can not include any sentences like “People not using AI in future will be replaced”, for a blog talking about the ‘importance of AI’. This idea is subjective and cannot be supported through research. 

Step 11, Grab Attention Immediately: Open with bold data, a surprising fact, a pressing problem, or a strong statement. Make sure these are not an empty rhetorical question or surface-level lead-in.

Step 12, Build Point-by-Point Persuasion: Keep sentences tight. Give an easy, logical transition from one to the next. Each sentence must be purposeful and build toward the main content. 

Step 13, Don’t find fancy and long-worded ways of making statements: Write to inform and not impress. Keep the explanations of the content simple, clear, and effective. For example, the usage of the sentence, "In the realm of digital content creation, leveraging algorithmically-driven methodologies to augment engagement matrices is paramount." must be avoided in favor of "To create engaging digital content, use AI tools that help increase reader interaction." This sentence is more direct and clear. 

Step 14, Avoid the usage of words with more than three syllables: Avoid the usage of words with more than three syllables unless very necessary. This is to avoid unnecessary complexity in the sentence structuring of the introduction. However, you should not apply this for the primary and secondary keywords.

Step 15, Prioritise the usage of the active voice: Prioritise the usage of the active voice in making the sentences of the introduction. Verbs have two voices—active and passive. When the verb is active, the subject of the sentence acts. When the voice is passive, the subject is acted upon. In the active voice, the subject is also the actor (the agent of the action). Their usage makes the sentences more dynamic and engaging. For example, the sentence, "The company launched a new AI tool." (Active), is direct and communicates the idea clearly in shorter words. This is not the case with the sentence, "A new AI tool was launched by the company." (Passive).

Step 16, Avoid the usage of the thinking verbs and prioritise the usage of the action verbs: The verb usage in the introduction must prioritise ‘action verbs’ over ‘thinking verbs’. Action verbs are those that depict a visible action. Their usage brings more clarity and impact on the readers. Their usage is ideal for blogs as it resonates more with the readers as they are more persuasive and dynamic. Some examples of action verbs are - think, analyze, decide, imagine, remember, understand, predict, solve, plan etc. Thinking verbs on the other hand depict cognitive processes. They are used for analyzing, reasoning, understanding, and making decisions. These verbs often refer to mental actions rather than physical ones. However, their usage is ideal only for highly analytical posts and research, as they give a more formal and critical tone to writing. Hence, they are ideal for academic writing and not blog posts. Some examples of thinking verbs are - understand, recognize, comprehend, realize, interpret, identify, distinguish etc. 

Step 17, Avoid the usage of adverbs: Adverbs are the words that modify verbs, adjectives or other verbs in a sentence by providing more information about how, when, where, or to what extent something happens. They help add detail and clarity to a sentence. For example, “He reached the destination quickly”. However, when writing the introduction, avoid the over-usage of adverbs ending with - ‘ly’ and use them only when they are very necessary. This is because it can cause unnecessary redundancy or over-explanation of a simple idea. For example, “She spoke softly”can be replaced with “She whispered”. 

Step 18, Avoid the usage of transitional words overused by ChatGPT: Transitional words are words and phrases that connect ideas smoothly within a sentence, between sentences, or across paragraphs. They guide the reader through your blog, ensuring a logical flow of thoughts. However, it is important to include them naturally and avoid the patterns of AI writing as they use them way too often unnecessarily. Make sure to limit the usage of the transitional words listed below and use them where it necessary:  
Accordingly; Additionally; Arguably; Certainly; Consequently; Hence; However; Indeed; Moreover; Nevertheless; Nonetheless; Notwithstanding; Thus; Undoubtedly; 

Step 19, Avoid the usage of adjectives overused by ChatGPT: Adjectives are words that describes a noun or pronoun or modifies their usage. They are used to make sentences more interesting and clear. However, they must not be used unnecessarily and avoid the patterns of AI writing which uses adjectives way too much. Make sure to limit the usage of the adjectives listed below and use them where it necessary:  
Adept; Commendable; Dynamic; Efficient; Ever-evolving; Exciting; Exemplary; Innovative; Invaluable; Robust; Seamless; Synergistic; Thought-provoking; Transformative; Utmost; Vibrant

Step 20, Avoid the usage of vital nouns overused by ChatGPT: Vital nouns are essential, meaningful, and impactful nouns that carry the core message of a sentence. They are used to make sentences more clear. For example, the usage of “The company saw growth” conveys less clarity than compared to "The company achieved a 40% increase in revenue." However, they must not be used unnecessarily and avoid the patterns of AI writing which uses vital nouns way too much. Make sure to limit the usage of the vital nouns listed below and use them where it necessary: 
Efficiency; Innovation; Institution; Integration; Implementation; Landscape; Optimization; Realm; Tapestry; Transformation;

Step 21, Avoid the usage of the verbs overused by ChatGPT: Make sure to use the verbs for describing actions in the sentence. However, they must not be used unnecessarily and avoid the patterns of AI writing which uses verbs way too much. Make sure to limit the usage of the verbs listed below and use them where it necessary: 
Aligns; Augment; Delve; Embark; Facilitate; Maximize; Underscores; Utilize 

Step 22, Avoid phrases overused by ChatGPT: Don’t include these phrases which are overused by Chatgpt and clearly indicate the patterns of AI writing for making sentences:


A testament to…; In conclusion…; In summary…; It’s important to note/consider…; It’s worth noting that…; On the contrary…etc.

Step 23, Avoid the usage of the data analysis phrases overused by ChatGPT:
Avoid the usage of these data analysis phrases overused by Chatgpt to avoid the patterns of AI wiring:

 “Deliver actionable insights through in-depth data analysis”; “Drive insightful data-driven decisions”; “Leveraging data-driven insights”; “Leveraging complex datasets to extract meaningful insights”.

Step 24, Avoid overly complex sentences with an unusual tone: This is one of the other signs that text may have been written by ChatGPT. Don’t include overly complex sentence structures with an unusually formal tone in text that’s supposed to be conversational or casual. Likewise, don’t include an overly casual tone for a text that’s supposed to be formal or business casual.
 
Step 25, Use simpler alternatives to unnecessary complex words: Swap the word(s) with their simpler alternatives for keeping the explanation of concepts simple:
Ways by which > Ways; Continues to be > Remains; In order to > To (especially at the beginning of a sentence); There (are) will be times when > Sometimes, At times; Despite the fact that > Although, Though; At which time > When; In spite of > Despite; When it comes to > In, When; The majority of > Most; A number of > Some, Few, Several, Many, Various (or often you don’t need to use any word at all); When asked > Asked; Leverage (as verb) > Use (or Put to use), Harness, Apply; The same level of > As much; While (if not being used to mean during or at the same time as) > Although or Though, Whereas; Moving forward > Later, In the future, From now on; Centered around > Centered on; Try and [verb] = Try to [verb]; Should of > Should have; At which time > When; In spite of > Despite; When it comes to > In, When; The majority of > Most; A number of > Some, Few, Several, Many, Various (or often you don’t need to use any word at all); When asked > Asked; Leverage (as verb) > Use (or Put to use), Harness, Apply; The same level of > As much; While (if not being used to mean during or at the same time as) > Although or Though, Whereas; Moving forward > Later, In the future, From now on; Centered around > Centered on; Try and [verb] = Try to [verb]; Should of > Should have
Step 26, Paragraph breaks: Cover only one broad idea in each paragraph. You must not overwhelm the users with a lot of information stacked in one paragraph. Take paragraph breaks after each broad idea is covered. This will give readers the time to clearly understand the content. 

Step 27, Grammatical accuracy: Ensure the grammatical accuracy of each sentence. This is vital for ensuring that you have taken due care in writing the content for your readers. Any inaccuracy will reflect lacking on your part to follow hygiene and lose the reader’s confidence and trust.  

Step 28, Give updated information: Give the latest and updated information about the concept covered in the blog title.  

Step 29, Avoid cliches: Avoid the usage of cliches in your text. Cliches are referred to as the expressions which are overused. Using them disappoints readers, as they are used to it in their daily lives and are not something which is new or unique. raft a unique hook relevant to the topic, avoiding clichés such as:  
 
 Ambience, Synergies, Thinking outside the box, The grass is greener, Time is money, At the end of the day, etc.

 Step 30, Link sentences and paragraphs: Every sentence and every paragraph should link to the one before it and point to the one that comes next. The readers must know, as they read each sentence and paragraph, why they are reading it and why they are reading it here, and why they are reading it now. The explanation you give in the introduction must establish one clear point, which is further advanced and clarified in your explanation.

Step 31, Avoid modifiers: A modifier is a word, phrase, or clause that modifies—that is, gives information about—another word in the same sentence. For example, in the following sentence, the word "burger" is modified by the word "vegetarian": Example: I'm going to the Saturn Café for a vegetarian burger. They are used to emphasise on an idea and communicate clarity. However, they can be uselessly applied, stretching the way an idea is explained. Some of the commonly used unnecessary modifiers are - actually, somewhat, virtually, almost, just, and really. Do not use them and take reference of alternatives of few examples of them and their simpler alternative:

the way in which [she spoke]→ the way [she spoke]; to the extent that [this matters]→ if [this matters]; as a result of the fact that→ because; owing to the fact that→ because; this is a [matter] that is important to make an application→this matters; the refurbishment of the building→ to apply; to effect a tackle→ to refurbish the building; it is recommended that training→ to tackle; be instigated→ [the department] should start training; he acted in an outrageous manner→ he acted outrageously; the writing of the book took him ten years→ the book took him ten years; in the most efficient manner → efficiently; I am going to go to bed soon → I am going to bed soon; I am going to sit and try to start to write→ I’m starting my book or I sit to write my book; she was tall in height→ she was tall; the question as to whether→ whether; at this point in time→ now

Step 32, Prioritise information in the present tense: You must ensure liveliness in all the sentences possible. Use as many present tense sentences as possible. They are the easiest, most direct, and strongest way to depict what a verb is doing in sentence. 

Step 33, Do not include vague terms: Do not use complex or abstract terms such as 'meticulous,' 'navigating,' 'complexities,' 'realm,' 'bespoke,' 'tailored,' 'towards,' 'underpins,' 'ever-changing,' 'ever-evolving,' 'the world of,' 'not only,' 'seeking more than just,' 'designed to enhance,' 'it’s not merely,' 'our suite,' 'it is advisable,' 'daunting,' 'in the heart of,' 'when it comes to,' 'in the realm of,' 'amongst,' 'unlock the secrets,' 'unveil the secrets,' and 'robust.' This approach aims to ensure that the content is direct, accessible, and easily interpretable.

Step 34, Avoid the usage of unnecessary adjectives: Adjectives are word that describes a noun, providing additional information about its qualities or characteristics. For example, in this sentence - “The villa is big.” “big” is an adjective. You must ensure that the usage of the adjectives is only done when necessary. Avoid the usage of unnecessary adjectives for exaggerating any idea. 

Step 35, Use a straightforward subject-verb-object order: Make sure that all the sentences in the content follow a straightforward subject-verb order. This will help you select words for their precision and avoid any chance of ambiguity.

Step 36, Do not take the liberty of making stats, facts, and figures from your end: Do not make any stats, facts, and figures from your end unless they can be traced back to their original source. 

Step 37, Avoid generic terms - Do not include generic terms like “imagine this”, or “picture this”, or out of context ‘coffee shop references’. These do not add any value to the content and the readers are able to easily identify the patterns of AI writing. 


Output:

Give the output in the markdown format
Do not acknowledge the completion of the task in your response.
Do not include any other heading or sub-headings from your end.
Do not mention word count split or distribution in the response. 
Use the research data to support your points and create authoritative, well-researched content that provides value to the reader. When citing data, ensure it comes directly from the provided research sources and follows the citation rules exactly.:
Citation rule: Mention the page link of the website and its name in the response after the information where it is used in the content.
Example: If the website name is EMB and the link is https://emb.global/seo then the 
Anchor Text Format: [[EMB](https://emb.global/seo)].
Do not start your response with ```markdown.
Maintain strict adherence to the word count instructions. 
Do not give the title of the blog post in the output.

"""

    return {
        "system": system_prompt.strip(),
        "user": user_prompt.strip()
    }
