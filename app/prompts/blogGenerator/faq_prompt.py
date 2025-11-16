from typing import Dict, List, Any, Union
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_faq_prompt(
    blog_request: Dict,
    project: Dict = None,
) -> dict[str, str]:
    """
    Generate the FAQ prompt for blog content generation.
    
    Args:
        blog_request: Dictionary containing blog request details
        project: Dictionary containing project details
    
    Returns:
        dict[str, str]: Dictionary containing system and user prompts with keys 'system' and 'user'
    """
    primary_keyword = blog_request.get('primary_keyword')
    secondary_keywords = ', '.join(blog_request.get('secondary_keywords', []))
    keyword_intent = blog_request.get('keyword_intent')
    target_audience_age_group = ', '.join(project.get('age_groups', [])) if project and project.get('age_groups') else 'general audience'
    industry = blog_request.get('industry')
    title = blog_request.get('blog_title')
    word_count = blog_request.get('word_count')
    outline = blog_request.get('outline')
    logger.info("--------------FAQ prompt------------------------------------------")
    logger.info("--------------------------------------------------------")
    logger.info(f"Primary Keyword: {primary_keyword}")
    logger.info(f"Secondary Keywords: {secondary_keywords}")
    logger.info(f"Keyword Intent: {keyword_intent}")
    logger.info(f"Target Audience: {target_audience_age_group}")
    logger.info(f"Industry: {industry}")
    logger.info(f"Title: {title}")
    logger.info(f"Word Count: {word_count}")
    logger.info(f"Outline: {outline}")
    # logger.info(f"Search Results: {search_results}")
    logger.info("-------------------End FAQ prompt-----------------------------------")
    logger.info("--------------------------------------------------------")

    faq_questions = ""
    section_headings = ""
    # Handle different outline structures
    if isinstance(outline, dict):
        # If outline is a dictionary with 'faqs' and 'sections'
        faq_questions = "\n".join([faq for faq in outline.get('faqs', [])])
        section_headings = ", ".join([s.get('heading', s.get('title', 'Untitled Section')) for s in outline.get('sections', [])])
        # Fallback for other structures
        
    logging.info(f"FAQ questions: {faq_questions}")
    logging.info(f"Section headings: {section_headings}")
    secondary_keywords = ", ".join(secondary_keywords)

    system_prompt = f"""You are a highly experienced SEO content writer who is well-versed in writing engaging SEO-friendly blogs. You need to produce high-quality answers for the FAQs of this blog by understanding the goals and process mentioned below. """

    user_prompt = f"""
    Generate straightforward answers for all FAQs about {title} in a single response.

Role
Act as a seasoned blog writer. Write the blog for the FAQs {faq_questions} mentioned from the outline {section_headings} mentioned below. Maintain the density of {primary_keyword} at 1.5% while building a natural connection with them. All the sentences must be grammatically correct. Include {secondary_keywords} naturally.

Input
Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords}
Intent: {keyword_intent}
Target Audience_Age Group: {target_audience_age_group}
Industry: {industry}
Title: {title}
Word Count: {word_count}
Outline: {outline}
Scraped data: {{}}


Goals 
Audience-focused: You need to first understand the audience and create content that matches their interest and need for reading the blog. By understanding the audience, you will know about the persona. Also, you will have a better context about the ideas and level of explanations to give in conclusion. Writing for a persona in mind makes the blog more engaging and chatty. A good blog conclusion always puts its users on the focus and resonates with them on a personal level.  This will ensure that you don’t include abstract, vague, and ambiguous elements in your writing.

Use Engaging Language and Structure: Avoid abrupt endings. The sentences must flow naturally while maintaining engagement. The conclusion should effortlessly transition from summarizing the content to reinforcing the reader’s next course of action.  

Use the Primary Keyword Naturally: Position the primary keyword in the answers of FAQs naturally such that it does not look enforced but also helps makes the content SEO friendly. 

Use simplified language: The tonality of the conclusion must be direct and must avoid unnecessary complex wordings. Replace complex phrases with simpler alternatives to improve relatability. Here are a few examples of that: In order to → To; Despite the fact that → Although; Leverage → Use; Utilize → Use, Subsequent → Next, following; Commence → Start, begin; Terminate → End, stop; Ascertain → Find out, determine; Facilitate → Help, ease, enable; Expedite → Speed up, accelerate; Implement → Carry out, apply, put in place; Disseminate → Share, spread; Mitigate → Reduce, lessen, ease; Enumerate → List, count; Comprehend → Understand, grasp; Obtain → Get; Procure → Get, acquire; Endeavor → Try, attempt; Illustrate → Show, explain; Indicate → Show, point out; Demonstrate → Show, prove; Substantial → Large, significant; Adequate → Enough, sufficient; Pertinent → Relevant, related; Consolidate → Combine, merge; Constitute → Make up, form; Rectify → Fix, correct; Optimize → Improve, make better; Articulate → Express, explain; Negate → Cancel, undo; Presume → Suppose, assume; Attain → Reach, achieve; Allocate → Give, assign; Engage in → Take part in, do; Accomplish → Complete, achieve; Contemplate → Think about, consider; Scrutinize → Examine, check; Advocate → Support, recommend; Enhance → Improve, boost; Elicit → Draw out, bring out



Sentence structuring: A sentence is a collection of words that contains a verb and a subject, on which it acts. They express an idea by making a statement or raising a question. The idea of the sentence is to simply say ‘who’ does ‘what’. Hence they must be clear and specific. They must be logically arranged in a paragraph to make a larger sense of the section explanation. You must intend to ‘inform’ and not impress the reader with the sentences in your content. 

Clear and simple explanations: Don’t find fancy and long-worded things to convey an idea. You must write to inform and not impress readers. Your each sentence must link with the other sentences and should be naturally placed. All the sentences of your answers must be clear and simple to understand. 

Reference the outline to build the context: While writing the answers for FAQs, take the reference of all the other headings in the blog also. This will help you answer the FAQs by fully knowing about the sections which the blog has covered. 

Avoiding redundancy and repetition: Avoid writing redundant ideas that are not directly related to answering FAQs. Keep the writing crisp and focused on solving users' problems. Furthermore, don’t repeat an idea once written. 

Coherence: Coherence refers to how well the ideas, sentences, and paragraphs flow. They help to build logical understanding of one sentence and one paragraph after another. This brings meaning to the content and ensures that the readers are able to clearly understand the concept. Ensure that the sentences and the paragraphs are naturally connected with each other. You can do this by using transitional words, with the caution of not repeating any idea or causing any redundancy. 
Straightforward answers to FAQs: Deliver straightforward answers that address common questions expected from readers, avoiding unnecessary complexity and ambiguity.



Process 

Understand the target audience: Understand the target audience for the blog and understand their interests, preferences, and needs for reading the blog. This will help you keep the focus on your reader and write ideas and explanations that talk rather than simply informing. By doing this you will have better ideas about giving ideas unique to them for writing answers. 

Understand the primary keyword and its intent: Understand the primary keyword and its intent to know about the kind of information you need to give in content. For example, if the blog is of Informational intent, then it must provide clarity, explanations, or background of the concepts. For e.g., if the blog is about “What is Digital Marketing”, then the blog sub-headings must be to explain the concepts related to it. Similarly, if it is of Navigational intent, then it must guide users to specific and targeted solutions. For eg., if the blog title is about ‘iPhone pricing’, then the user must receive the various pricing options as the user is already beyond the need for getting surface-level explanations. For Commercial intent, it must help users compare, evaluate, or make decisions. For e.g., for the blog topic "SEO vs. SEM: Which Strategy Suits Your Business?", blog sub-headings must list the advantages and disadvantages for both as the users are in the decision-making stage. For Transactional intent, the content must direct users toward action-oriented content. For e.g., "How to Optimize Your Website for SEO in 5 Steps", provides clear steps for achieving this in the sub-headings. This alignment has to be further based on the category and sub-category of the blog which are based on the user selections, and clearly tells about the kind of sub-headings the users are expecting. For e.g., in a blog titled “How to Create a Sales Plan?”, the blog is of the ‘Action-Oriented’ category and ‘How-To sub-category’. For this blog, the sub-headings must give clear actionable steps for creating the sales plan and can avoid surface-level sub-headings like What is a sales plan, Importance of Sales Plan, etc. 

Understand the secondary keywords: Understand the secondary keywords to understand the context in which the information of the primary keyword has to be covered. For example, for the primary keyword ‘email marketing benefits’, the secondary keyword ‘automation in email marketing’, establishes the need for highlighting the benefits of email marketing and gives a special emphasis on ‘automation’, as one of the benefits of email marketing. Based on this you will get the headings and sub-headings in the blog outline, and you must build relationships with the primary keyword, secondary keyword, the blog title, and the heading of the section to give the content accordingly. This will help you ensure that you don’t give the answers out of context and the readers are able to build a natural relation. 

Alignment with the blog title: You must factor the title of the blog to directly understand the user’s expectations from the blog. The title of the blog clearly set the goal of what, why, and how the content should be written. The answers should align with the title of the blog to give a natural understanding of the concept in the entire blog post to the reader. For example, for a blog titled ‘Choosing the Right Mutual Funds to Invest’, you must write answers aligned with the reader’s need for taking the decision. 

Adjust the complexity level based on audience: Adjust the complexity of information based on the reading grade of the audience. For example, if the target audience for the blog for the primary keyword ‘ai trends’, is school-going kids studying, lying between the age of 12-15 years, then the expectation of the reader would be to have surface-level information about the concepts, just to get the awareness on the subject. On the other hand, if the audience is from the ‘technology industry’, falling in the age group of 25-40 years, then they are expecting very precise, accurate, and actionable information. Hence the sub-headings have to go beyond surface-level explanations in this case, assuming that the readers already are aware of it and they are looking for a credible source to expand their knowledge.

Understand the outline of the blog: Understand the outline of the blog to know about the section for which you have to write. Based on this, know about the context of writing the answers and include information and ideas based on this. By understanding the outline of the blog you will come to know about the other headings and sub-headings which are to be covered in a final blog output. Write the answers based on this only to ensure that the answers reflects coherence in the final blog output. Hence, do not write the answers in vanity and ensure the natural flow of the overall blog content, by not writing answers with a standalone approach. 

Alignment with the word count: Include a maximum of 75 words for answering any FAQ.

Do not include subjective ideas: Do not include any subjective ideas from your end. All the sentences for writing the answers must be logical and factually accurate. Don’t express your personal beliefs and take the support of facts and research only to establish a point. For example, you can not include sentence like,  “People not using AI in future will be replaced”, for a section talking about the ‘importance of AI’. This idea is subjective and cannot be supported through research. 

Don’t find fancy and long-worded ways of making statements: Write to inform and not impress. Keep the explanations of the content simple, clear, and effective. For example, the usage of the sentence"In the realm of digital content creation, leveraging algorithmically-driven methodologies to augment engagement matrices is paramount." must be avoided in favor of "To create engaging digital content, use AI tools that help increase reader interaction." This sentence is more direct and clear. 

Avoid the usage of words with more than three syllables: Avoid the usage of words with more than three syllables unless very necessary. This is to avoid unnecessary complexity in the sentence structuring of the answers. However, you should not apply this for the primary and secondary keywords of the content and the necessary explanations of the concept relating to it. 

Prioritise the usage of the active voice: Prioritise the usage of the active voice in making the sentences of the section content. Verbs have two voices—active and passive. When the verb is active, the subject of the sentence acts. When the voice is passive, the subject is acted upon. In the active voice, the subject is also the actor (the agent of the action). Their usage makes the sentences more dynamic and engaging. For example, the sentence, "The company launched a new AI tool." (Active), is direct and communicates the idea clearly in shorter words. This is not the case with the sentence, "A new AI tool was launched by the company." (Passive).

Avoid the usage of the thinking verbs and prioritise the usage of the action verbs: The verb usage in the conclusion must prioritise ‘action verbs’ over ‘thinking verbs’. Action verbs are those that depict a visible action. Their usage brings more clarity and impact on the readers. Their usage is ideal for blogs as it resonates more with the readers as they are more persuasive and dynamic. Some examples of action verbs are - think, analyze, decide, imagine, remember, understand, predict, solve, plan etc. Thinking verbs on the other hand depict cognitive processes. They are used for analyzing, reasoning, understanding, and making decisions. These verbs often refer to mental actions rather than physical ones. However, their usage is ideal only for highly analytical posts and research, as they give a more formal and critical tone to writing. Hence, they are ideal for academic writing and not blog posts. Some examples of thinking verbs are - understand, recognize, comprehend, realize, interpret, identify, distinguish etc. 

Avoid the usage of adverbs: Adverbs are the words that modify verbs, adjectives or other verbs in a sentence by providing more information about how, when, where, or to what extent something happens. They help add detail and clarity to a sentence. For example, “He reached the destination quickly”. However, when writing the answers, avoid the over-usage of adverbs ending with - ‘ly’ and use them only when they are very necessary. This is because it can cause unnecessary redundancy or over-explanation of a simple idea. For example, “She spoke softly” can be replaced with “She whispered”. 

Avoid the usage of transitional words overused by ChatGPT: Transitional words are words and phrases that connect ideas smoothly within a sentence, between sentences, or across paragraphs. They guide the reader through your blog, ensuring a logical flow of thoughts. However, it is important to include them naturally and avoid the patterns of AI writing as they use them way too often unnecessarily. Make sure to limit the usage of the transitional words listed below and use them where it is necessary:  
Accordingly; Additionally; Arguably; Certainly; Consequently; Hence; However; Indeed; Moreover; Nevertheless; Nonetheless; Notwithstanding; Thus; Undoubtedly; 

Avoid the usage of adjectives overused by ChatGPT: Adjectives are words that describe a noun or pronoun or modify their usage. They are used to make sentences more interesting and clear. However, they must not be used unnecessarily and avoid the patterns of AI writing which uses adjectives way too much. Make sure to limit the usage of the adjectives listed below and use them where it necessary:  
Adept; Commendable; Dynamic; Efficient; Ever-evolving; Exciting; Exemplary; Innovative; Invaluable; Robust; Seamless; Synergistic; Thought-provoking; Transformative; Utmost; Vibrant

Avoid the usage of vital nouns overused by ChatGPT: Vital nouns are essential, meaningful, and impactful nouns that carry the core message of a sentence. They are used to make sentences more clear. For example, the usage of “The company saw growth” conveys less clarity than compared to "The company achieved a 40% increase in revenue." However, they must not be used unnecessarily and avoid the patterns of AI writing which uses vital nouns way too much. Make sure to limit the usage of the vital nouns listed below and use them where it necessary: 
Efficiency; Innovation; Institution; Integration; Implementation; Landscape; Optimization; Realm; Tapestry; Transformation;

Avoid the usage of the verbs overused by ChatGPT: Make sure to use the verbs for describing actions in the sentence. However, they must not be used unnecessarily and avoid the patterns of AI writing which uses verbs way too much. Make sure to limit the usage of the verbs listed below and use them where it necessary: 
Aligns; Augment; Delve; Embark; Facilitate; Maximize; Underscores; Utilize 

Avoid phrases overused by ChatGPT: Don’t include these phrases which are overused by Chatgpt and clearly indicate the patterns of AI writing for making sentences:
A testament to…In conclusion… In summary… It’s important to note/consider… It’s worth noting that… On the contrary….

Avoid the usage of the data analysis phrases overused by ChatGPT:
Avoid the usage of these data analysis phrases overused by Chatgpt to avoid the patterns of AI wiring:
 “Deliver actionable insights through in-depth data analysis”; “Drive insightful data-driven decisions”; “Leveraging data-driven insights”; “Leveraging complex datasets to extract meaningful insights”.

Avoid overly complex sentences with an unusual tone: This is one of the other signs that text may have been written by ChatGPT. Don’t include overly complex sentence structures with an unusually formal tone in a text that’s supposed to be conversational or casual. Likewise, don’t include an overly casual tone for a text that’s supposed to be formal or business casual.
 
Use simpler alternatives to unnecessary complex words: Swap the word(s) with their simpler alternatives for keeping the explanation of concepts simple:
Ways by which > Ways; Continues to be > Remains; In order to > To (especially at the beginning of a sentence); There (are) will be times when > Sometimes, At times; Despite the fact that > Although, Though; At which time > When; In spite of > Despite; When it comes to > In, When; The majority of > Most; A number of > Some, Few, Several, Many, Various (or often you don’t need to use any word at all); When asked > Asked; Leverage (as verb) > Use (or Put to use), Harness, Apply; The same level of > As much; While (if not being used to mean during or at the same time as) > Although or Though, Whereas; Moving forward > Later, In the future, From now on; Centered around > Centered on; Try and [verb] = Try to [verb]; Should of > Should have; At which time > When; In spite of > Despite; When it comes to > In, When; The majority of > Most; A number of > Some, Few, Several, Many, Various (or often you don’t need to use any word at all); When asked > Asked; Leverage (as verb) > Use (or Put to use), Harness, Apply; The same level of > As much; While (if not being used to mean during or at the same time as) > Although or Though, Whereas; Moving forward > Later, In the future, From now on; Centered around > Centered on; Try and [verb] = Try to [verb]; Should of > Should have
Paragraph breaks: Cover only one broad idea in each paragraph. You must not overwhelm the users with a lot of information stacked in one paragraph. Take paragraph breaks after each broad idea is covered. This will give readers the time to clearly understand the content.
 
Grammatical accuracy: Ensure the grammatical accuracy of each sentence. This is vital for ensuring that you have taken due care for writing the content for your readers. Any inaccuracy will reflect that lacking on your part to follow hygiene and lose reader’s confidence and trust. 
 

 Give only unique and highly relevant information: Do not include redundant information to elaborate on the section heading. Give only unique and highly relevant information that gives readers information that cannot be simply understood just by reading the section heading. For example, for a section talking about ‘importance of digital marketing’, merely including the text ‘digital marketing is very important these days and no business must miss it’, will not do the job as the information is not unique and can be simply understood by the reader just by reading the section heading.  

Avoid cliches: Avoid the usage of cliches in your text. Cliches are referred to as the expressions which are overused. Using them disappoints readers, as they are used to it in their daily lives and are not something which is new or unique. raft a unique hook relevant to the topic, avoiding clichés such as:  
 
 Ambience, Synergies, Thinking outside the box, The grass is greener, Time is money, At the end of the day, etc.

Avoid modifiers: A modifier is a word, phrase, or clause that modifies—that is, gives information about—another word in the same sentence. For example, in the following sentence, the word "burger" is modified by the word "vegetarian": Example: I'm going to the Saturn Café for a vegetarian burger. They are used to emphasise on an idea and communicate clarity. However, they can be uselessly applied, stretching the way an idea is explained. Some of the commonly used unnecessary modifiers are - actually, somewhat, virtually, almost, just, and really. Do not use them and take reference of alternatives of few examples of them and their simpler alternative:

the way in which [she spoke] → the way [she spoke]; to the extent that [this matters] → if [this matters]; as a result of the fact that → because; owing to the fact that → because; this is a [matter] that is important to make an application → this matters; the refurbishment of the building → to apply; to effect a tackle → to refurbish the building; it is recommended that training → to tackle; be instigated → [the department] should start training; he acted in an outrageous manner → he acted outrageously; the writing of the book took him ten years → the book took him ten years; in the most efficient manner → efficiently; I am going to go to bed soon → I am going to bed soon; I am going to sit and try to start to write → I’m starting my book or I sit to write my book; she was tall in height → she was tall; the question as to whether → whether; at this point in time → now

Prioritise information in the present tense: You must ensure liveliness in all the sentences possible. Use as many present tense sentences as possible. They are the easiest, most direct, and strongest way to depict what a verb is doing in sentence. 

Do not include vague terms: Do not use complex or abstract terms such as 'meticulous,' 'navigating,' 'complexities,' 'realm,' 'bespoke,' 'tailored,' 'towards,' 'underpins,' 'ever-changing,' 'ever-evolving,' 'the world of,' 'not only,' 'seeking more than just,' 'designed to enhance,' 'it’s not merely,' 'our suite,' 'it is advisable,' 'daunting,' 'in the heart of,' 'when it comes to,' 'in the realm of,' 'amongst,' 'unlock the secrets,' 'unveil the secrets,' and 'robust.' This approach aims to ensure that the content is direct, accessible, and easily interpretable.

Avoid the usage of unnecessary adjectives: Adjectives are words that describe a noun, providing additional information about its qualities or characteristics. For example, in this sentence - “The villa is big.” “big” is an adjective. You must ensure that the usage of the adjectives is only done when necessary. Avoid the usage of unnecessary adjectives for exaggerating any idea. 

Use a straightforward subject-verb-object order: Make sure that all the sentences in the content follow a straightforward subject-verb order. This will help you select words for their precision and avoid any chance of ambiguity.

Do not take the liberty of making stats, facts, and figures from your end: Do not make any stats, facts, and figures from your end unless they can be traced back to their original source. 

Avoid generic terms - Do not include generic terms like:
 “In conclusion…”  ;  “In summary…”; “At the end of the day…” ; “So now you know all about…” ; “To sum it all up…” ; “It is important to note that…” 
These do not add any value to the content and the readers are able to easily identify the patterns of AI writing. Instead, allow the conclusion to naturally signal the end rather than using formulaic wrap-ups. 




Output:

Do not acknowledge the completion of the task in your response.
Do not include any other heading or sub-headings from your end.
Use the research data to support your points and create authoritative, well-researched content that provides value to the reader. When citing data, ensure it comes directly from the provided research sources and follows the citation rules exactly.:
Add proper new line between each faqs.


Each faq should have a question and an answer in the below format:-
Question: Question 1 
Answer: Answer 1 

Question: Question 2 
Answer: Answer 2 

Question: Question 3 
Answer: Answer 3 

Question: Question 4 
Answer: Answer 4 

Question: Question 5 
Answer: Answer 5

    """

    return {
        "system": system_prompt,
        "user": user_prompt
    }
