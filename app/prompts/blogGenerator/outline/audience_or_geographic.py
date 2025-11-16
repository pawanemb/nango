from typing import List,Dict
from datetime import datetime
def audience_or_geographic_prompt(
        blog_title: str,
        primary_keyword: str, 
        secondary_keywords: List[str],
        keyword_intent: str,
        industry: str,
        word_count: str, 
        country: str,
        category: str,
        subcategory: str,
        project: Dict = None
    ) -> str:
        """Generate prompt for creating blog outline."""
        secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else ""
        age_groups_str = ", ".join(project["age_groups"]) if project["age_groups"] else ""
        gender_str = ", ".join(project["gender"]) if project["gender"] else ""
        language = ', '.join(project.get('languages', [])) if project and project.get('languages') else 'English (UK)'
        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
Input
Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords_str}
Blog Category: {category}
Blog Sub-Category: {subcategory}
Intent: {keyword_intent}
Word Count: {word_count}
Target Audience_Age: {age_groups_str}
Industry: {industry}
Title: {blog_title}
Target Language: {language}
Keyword Location: {country}
Target Gender: {gender_str}
Current Date: {current_date}

Goals
Create a blog outline that achieves the following goals in your response :
Audience-focused: Adjust the complexity of information based on the reading grade of the audience. For example, if the target audience for the blog for the primary keyword ‘ai trends’, is school-going kids studying, lying between the age of 12-15 years, then the expectation of the reader would be to have surface-level information about the concepts, just to get the awareness on the subject. On the other hand, if the audience is falling in the age group of 25-40 years, then they are expecting very precise, accurate, and actionable information. Hence the sub-headings have to go beyond surface-level explanations in this case, assuming that the readers already are aware of it and they are looking for a credible source to expand their knowledge.
Well-structured: Ensure a natural reading experience. All headings and sub-headings must be organized in a logical way. Do not go off-topic. If you are writing a blog about a historical event, it makes sense to have headings or sub-headings appear in chronological order. If you are writing a blog to improve a law, it makes sense to have headings or sub-headings appear in the order of steps one would have to take. If you are writing a blog about fashion tips, it makes sense to group these tips by objective like makeup tips, party wear tips, accessory tips, etc.
Alignment with intent: Ensure that the blog sub-headings are aligned with the intent of the blog and must solve the problem of the users specific to their intent. 
For example, if the blog is of Informational intent, then it must provide clarity, explanations, or background of the concepts. For e.g., if the blog is about “What is Digital Marketing”, then the blog sub-headings must be to explain the concepts related to it. 
Similarly, if it is of Navigational intent, then it must guide users to specific and targeted solutions. For eg., if the blog title is about ‘iPhone pricing’, then the user must receive the various pricing options as the user is already beyond the need for getting surface-level explanations. 
For Commercial intent, it must help users compare, evaluate, or make decisions. For e.g., for the blog topic "SEO vs. SEM: Which Strategy Suits Your Business?", blog sub-headings must list the advantages and disadvantages for both as the users are in the decision-making stage. 
For Transactional intent, the outline must direct users toward action-oriented content. For e.g., "How to Optimize Your Website for SEO in 5 Steps", provides clear steps for achieving this in the sub-headings. This alignment has to be further based on the category and sub-category of the blog which are based on the user selections, and clearly tells about the kind of sub-headings the users are expecting. For e.g., in a blog titled “How to Create a Sales Plan?”, the blog is of the ‘Action-Oriented’ category and ‘How-To sub-category’. For this blog, the sub-headings must give clear actionable steps for creating the sales plan and can avoid the surface-level sub-headings like What is a sales plan, Importance of Sales Plan, etc.  
Inclusion of Primary and Secondary Keywords: Ensure that the blog outline incorporates the primary and secondary keywords as received in the input to ensure coverage of the concepts. By doing this, the blog sub-headings must directly solve the problem of the users, and avoid incorporating abstract ideas, and vague and redundant sub-headings as they are not useful and helpful to the reader. Also, make sure that the keywords are included naturally within the sub-headings, and the compulsive stuffing of keywords is not done for the sake of SEO optimisation as it hampers the reader’s trust in the blog.  For eg., a blog with the primary keyword of AI trends, and secondary keywords of Gen AI, Machine Learning, and NLP, highlights the need of the user to study the trends with respect to the latest advancements. 
Include unique perspectives: Make sure that all the headings and subheadings support the in-depth coverage of content on the blog. In doing this, ensure that all the headings and subheadings support a unique perspective that the readers might not find otherwise and are solving their problem. Based on this, give only the most important subheadings in the outline, which fit the word count constraints of the blog. For eg., for the blog titled “How to Overcome Audio Quality Issues with Wireless Studio Monitor Headphones”, with a word count limit of 1000 words, prioritise giving the most important suggestions for the problem while doing justice to the word count limit. Hence, avoid giving filler sub-headings like ‘Importance of Headphones’, ‘About Headphones’, etc.
Apt Outline breakdown: Include Main Sections (further broken down in headings and sub-headings via H2, H3), Conclusion, and FAQs. Give a Conclusion before the FAQs and always keep the FAQs at the last of the outline section.
Choose the right H2 and H3: Understand the title and lay more emphasis on important topics and reduce emphasis on unimportant details. Do not include redundant details. Do not repeat information unless absolutely necessary. Do not include examples and case studies as separate headings unless the blog title talks about the need for it. 
Adherence with EEAT guidelines: Ensure the outline includes sub-headings that help the blog adhere to the E-E-A-T (Experience, Expertise, Authoritativeness, and Trustworthiness) principles. This principle entails the need for creating relevant and quality blogs as search engines like Google evaluate content based on this principle for ranking the content. To achieve this, you must focus on creating outline sections that bring value to readers and match their interests. To evaluate the interest of the readers with respect to any blog post, establish the relationship between the primary and secondary keywords selected by the users and further understand the intent of the keywords (especially the primary keyword) and understand its synergy with the category and the sub-category selected by the user for producing the content. By doing this you can integrate elements that establish subject matter expertise and credibility throughout the outline.

Understand Language Preference: Understand the language preference of the blog text between English (UK) and English (USA). You must write the content based on this only. For example, if the user has selected English (UK) as their language preference, then words like 'recognize' must be written as 'recognise' to support the preference.

 Use Simplified Language:  The tonality of the sub-headings must be direct and must avoid unnecessary complex wordings. Replace complex phrases with simpler alternatives to improve relatability. Here are a few examples of that: In order to → To; Despite the fact that → Although; Leverage → Use; Utilize → Use, Subsequent → Next, following; Commence → Start, begin; Terminate → End, stop; Ascertain → Find out, determine; Facilitate → Help, ease, enable; Expedite → Speed up, accelerate; Implement → Carry out, apply, put in place; Disseminate → Share, spread; Mitigate → Reduce, lessen, ease; Enumerate → List, count; Comprehend → Understand, grasp; Obtain → Get; Procure → Get, acquire; Endeavor → Try, attempt; Illustrate → Show, explain; Indicate → Show, point out; Demonstrate → Show, prove; Substantial → Large, significant; Adequate → Enough, sufficient; Pertinent → Relevant, related; Consolidate → Combine, merge; Constitute → Make up, form; Rectify → Fix, correct; Optimize → Improve, make better; Articulate → Express, explain; Negate → Cancel, undo; Presume → Suppose, assume; Attain → Reach, achieve; Allocate → Give, assign; Engage in → Take part in, do; Accomplish → Complete, achieve; Contemplate → Think about, consider; Scrutinize → Examine, check; Advocate → Support, recommend; Enhance → Improve, boost; Elicit → Draw out, bring out
Giving Useful, Credible, and Relevant Information in Sections: Alignment with the E-E-A-T principles is a must. You must ensure that all the heading and sub-heading level information is factually correct, credible, and updated as if the expert on the subject has written about it.  The section headings should go beyond surface-level topic suggestions unless very necessary. 

For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, or “shortcuts”, strictly avoid any top-of-the-funnel section headings such as attempt to explain ‘why it is important’, ‘what it is’, or ‘why you should do it’ as separate H2s.
Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines unless very necessary.
Give headings and sub-headings which supports interactive formatting options: Give headings and sub-headings which apart from supporting text supports interactive formatting options upon writing the blog. These include:
i. Lists


Bulleted lists (•)
Numbered lists (1, 2, 3)
Checklists (✓)
Nested lists


ii. Tables


Simple 2-column tables (term vs definition)
Multi-column tables (side-by-side comparisons)
Highlighted rows and columns for emphasis


iii. Block Formatting
Blockquotes (“ ”)
Pull quotes
Code blocks (for technical content)


iv. Text Emphasis


Bold for keywords/numbers
Italics for subtle emphasis
Monospace for commands/filenames
Occasional ALL CAPS / small caps for emphasis


v. Dividers & Breaks


Section dividers (•••)
Pros vs Cons lists
Timelines (Year → Event)
n. Do not give the predictable number of sub-headings in the outline: Avoid taking a templatised approach of giving the same number of sub-headings for all the heading sections. The number of sub-headings must be logical as per their respective heading section name. Vary the number of sub-headings sections thus wherever possible. Try to bring variance for every consecutive heading. However, in doing this, prioritise the comprehensiveness of information to cover through the outline. This is critical for the success of the task and the test of your ability. 
o. Multi-intent coverage: Structure the outline to serve clusters of intents across AI, search, and social. Each main section must map to one micro-intent: informational, comparative, transactional, or community-driven. Avoid keyword-only thinking—optimise for entities and relationships.


o. Prioritise the usage of active voice and present tense in your response: Make sure to keep the headings and sub-headings interactive and participative. Prioritise the usage of active voice and present tense in the headings and sub-headings section name. 
p. Take a direct approach in giving the subsections heading, directly indicating what the readers will find in this section. Keep the character limit restrained for sub-headings to 30 characters at max. Ignore this instruction only when very necessary.
q. Break the predictable pattern of giving the same number of subsections for the heading. Take a natural approach of giving a diverse number of subsections depending on its heading. Do this in such a way that is highly relevant to the heading and does not contain any unnecessary subsections that might not be required. Follow this instruction very strictly as it is a direct test of your ability to perform this task. 

Process:

Step 1, Understanding Primary and Secondary Keywords and their Role: You must ensure that the primary keyword and the secondary keywords are included in the blog headings and sub-headings. For this, it is important that you incorporate these keywords naturally within the headings and subheadings to establish a natural connection with the users. The usage of the secondary keywords must complement the primary keyword and guide the writers to include information about the primary keyword with context. For example, if a primary keyword is ‘AI trends’, and the secondary keywords for the post are ‘Generative AI’, ‘NLP’, ‘Open Source LLMs’, etc., then the sub-headings must have a clear focus on writing the headings and subheadings that most importantly focuses on the AI trends and include the sub-headings mentioned as the secondary keywords as they are the most important and relevant to the primary keyword ‘AI trends’. 

Step 2, Create an Outline for Audience or Geography Specific Blog: To do this, you must understand the purpose of the category. Audience or geography specific blogs are meant for a targeted audience falling under a specific demographic group or belonging to a particular geography. You have to understand the very specific preferences of the geography, culture or unique concerns of the demographic group. These are highly relevant blogs, and have a limited appeal to the readers outside the target group. For example, for a blog topic ‘How Millennials Are Redefining Career Goals in India’, the blog will not resonate with boomers or gen alpha. For blogs catering to localised interests, specific research on the regional trends and preferences would be required. Likewise, for the blogs catering to a demographic interest, research on the demographic preferences, trends, and habits would be required. This enables the blog to uniquely solve the challenges of the target groups.


Dos for writing the headings and sub-headings of audience or geography focused blog:

Understand whether to write a demography-based blog outline or geography-based blog outline from the title:  Understand the blog title to understand if the blog needs to cater to the demographic or geographical audience. For example, for a blog talking about ‘fashion trends for GenZ’, the blog requires demographic specific headings and sub-headings. Similarly, for the blog talking about ‘resource augmentation in the United States’, the blog requires geography level information, headings, and sub-headings. 

Give a cultural point of view: Give a cultural point of view wherever necessary to make the blog relevant. For example, for a blog talking about the ‘fashion trends in Middle East’, including the cultural point of the audience in the geography will resonate with the audience better. 

Address the readers directly based on their region or demography: Maintain the headings and sub-headings that directly talks with the readers in a certain demographic group or geography. This will ensure that the blog headings and sub-headings level ideas are not generic. For example, for a blog targeted towards e-commerce store owners in India, include headings like ‘Offer Festive Sales in Festive Seasons of Holi and Diwali’, instead of ‘Offer Promotional Discounts’. 

Focus on highlighting trends: Give the headings and sub-headings with updated information and recent trends in the geographic area or demographic group. 

Maintain regional sensitivities for regional blogs: Respect the regional, cultural and religious sensitives of the regional audience to ensure that they are not offended. For example, for a blog talking about ‘ethnic fashion advice’, for a Middle East audience, giving ‘western clothing advice’ will negatively impact the blog. 

Include local details for regional blogs: Support your blogs and sub-headings which have the scope for including local information. This will make the blog more relatable and better appeal to the needs of the reader. For example, for a blog talking about ‘local fashion trends of India’, talking about ‘Banarsi saree, or Pashmina shawl’, will make the information more valuable. 

Take inspiration from local stories or events for regional blogs: Take the reference of the well known incidents, cultural moments, and case studies will resonate with the target audience well. For example, for a blog titled “How Indian E-Commerce Stores Can Win Customers in 2025", referencing the adoption of the UPI will make the information more directed and relatable to the Indian audience. 

Use factually accurate and updated information: Use only the facts, stats and researches to ensure the accuracy of the information of the headings and sub-headings.

Include numbered lists to clearly break down texts: Break down the headings and sub-headings into simpler levels of explanation, covering only aspects of the concept in one heading. Make the use of the numbered lists in the headings and sub-headings to ensure organization of key points, methods, steps, process, etc.  


Don’ts for writing the headings and sub-headings of audience or geography focused blog:


Don’t make generalized assumptions and statements which are not factual: Only reference the facts, stats, research to give headings and sub-headings. Don’t give generalized information like ‘sustainable fashion is popular in the USA’, without taking the reference of a research which supports this. 

Avoid generic blog headings and sub-headings: Don’t give generic blog headings and sub-heading only with the surface level knowledge. Give the blog headings and sub-headings which are direct and tailored to the interests of the target group. For example, for a blog dealing with the ‘ecommerce store trends in India’, avoid generic heading like “Digital Transactions Bring Ease of Business” in favor of “Integrate UPI Payment Options”.

Don’t promote stereotypes: Do not make assumptions and don’t give headings, sub-headings or any piece of information which is stereotypical. For example, for a blog talking about "Safety of Women in Indian Workspace”, don’t include stereotypes like ‘Indian males are chauvinist’. 

Don’t focus on highlighting what other target groups do unless necessary: Don’t include information about the other target groups and keep the focus on the target group unless necessary. For example, a blog talking about ‘What GenZ thinks about AI’, doesn't communicate what ‘GenAlpha’ thinks about it. 

Don’t include repetitive information: Don’t repeat the headings and sub-headings in the blog unless very necessary. 

Don’t give exclusive details in sub-headings- Don’t give the sub-headings which do not relate to its heading and contain entirely different information. 

Don’t include information not specific to the preference of the target group: Don’t give information which is not specific to the target group addressed in the blog. Don;t give headings and sub-headings which do not uniquely relate to the use case of the target group. For example the heading of ‘Enabling Digital Payment Methods’ for a blog talking about the ‘Ways of Improving Ecommerce Store Sales in India’ will be too generic. 

Step 3: Direct Alignment with the Blog Title: You must factor in the title of the blog to directly understand the user’s expectations from the blog. You must give the blog headings and sub-headings based on this only and do not include any redundancies and vagaries. Furthermore, you must ensure that the blog headings and sub-headings must uniquely address the concepts relating to the title and you do not repeat any heading and sub-heading unless very necessary. For instance, if the blog title is “10 Most Important Tools in Email Marketing”, then your focus must be on giving the list of such tools in the sub-headings irrespective of the word count instructions you receive. Likewise, if the blog title is about “What is Digital Marketing”, then your headings and subheadings must be to ensure that the readers are able to understand the concept by answering the query in the title directly. 
 
Step 4: Maintaining Word Count Instructions: Ensure that the number of H2s strictly matches the word count criteria. Always validate the count before returning the final output.
 Sub-heading Count Based on Word Count:
For 350 words:  
Sritctly include only 1 H2.
Include  a maximum of 3 most important H3s, directly addressing the concept or query mentioned in the title. 
Do not cover the foundational understanding of the topic unless required.
Override the number of H3 instruction if the blog title includes a fixed number (e.g., '10 tools', '5 steps' etc.) and give the outline accordingly.
For 850 words: Strictly include only 1-2 H2s 
For 1250 words: Strictly include only 2-3 H2s 
For 2000 words: Strictly include only 3-5 H2s
Make sure that each sub-heading you give supports a minimum of 50 words and a maximum of 250 words such that the information mentioned within it is written by a human without any fillers and redundancies for giving the most valuable information to the readers aligned with the E-E-A-T principles of writing helpful content. 
For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, or “shortcuts”, DO NOT include any introduction-style or top-of-the-funnel explainers like 'Why this is important', or 'What this means'. Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines.
Prioritise the importance of concepts to be included in the headings and sub-headings based on the word count and give the most important sections only with respect to the word count. 
If the blog title includes a fixed number (e.g., '10 tools'), override word count logic and give exactly that number of H2s. Otherwise, enforce H2 count strictly based on the word count.
For example, for a blog talking about ‘6 ways to improve digital marketing’, give 6 H2s even if the word count selection is of 1000 words. Furthermore, ensure that the reason why the number is mentioned in the title of the blog is fully catered. For example, for a blog talking about the ‘6 ways to improve your digital marketing’, make sure you give 6 ways in H2, apart from including other H2s like Introduction, Conclusion etc. 
Step 5: Ensuring the Ease of Reading: To ensure ease of reading, do not apply the formulaic approach of creating H3 level sub-headings for every H2 level heading. This is to ensure that only the most important sub-headings are given in the output and the scope of redundancies is reduced. For instance, you can skip H3 level headings which offer only top-of-the-funnel explanations of the concepts.  For eg., the blog sub-heading about ‘What is Digital Marketing’ might not require further sub-headings as the users are simply expecting the answer to this question.

Step 6: User-Friendly Language: Avoid the usage of words with more than three syllables in the headings and sub-headings. This will ensure that the headings and sub-headings are easy to read. However, make exceptions for primary and secondary keywords as they have to be used as it is in the content and their headings and sub-headings. The objective of this is to ensure that the headings and subheadings speak to the reader and are engaging. Furthermore, the verb usage in the headings and sub-headings must prioritise ‘action verbs’ over ‘thinking verbs’. 
Step 7: Heading and Sub-heading Character Limit: Maintain the character limit of 65 characters for all the headings so that the readers are able to digest them and are able to recall them even in a skim reading on a device like a mobile phone.  In doing this, make sure that all the section sub-headings are less than 45 characters, directly telling what this section will do. 


Step 8: The blog Outline Structure has to be the following: 
Sections (Numbers depending on the word count), Conclusion, FAQs. Maintaining this structure ensures that the blog outline is properly formatted and the blog looks complete.  The users must not be left wondering - ‘what next’, or ‘why this’. 
Do not include the Introduction as the heading in the outline response as it looks redundant and self-explanatory. Thus, begin directly with the section headings arranged chronologically, following a logical order and then include FAQs at the end followed by a Conclusion.



Step 9: FAQs: Do not give FAQs before the conclusion. FAQs. Ensure that FAQs are popular questions related to the blog title. Ensure they cover both basic and advanced doubts. To determine which question is more relevant, think about what questions might a person think about when they are about to implement the knowledge they just learnt in the blog. Do not answer the FAQs. The structure of FAQs should be such that the density of primary keywords is maintained at 1% and furthermore the secondary keywords are included, building a natural connection with the readers. Include 3-6 FAQs in the response. However, for the word count input of 350 words, give a maximum of 3 FAQs. Make sure to include the FAQs, whose answer provides the latest and updated information. FAQs should only and only be given after the conclusion.

Output:	
Give the output in the JSON format.
Do not give explanations of the headings and subheadings.
Do not acknowledge the completion of the task in your response. 
Give FAQs after the conclusion.
Give Conclusion before the FAQs.
When giving output, do not write "```json" or "```"
Remove the markdown formatting and other special symbols from the output. 
Do not include em dash (—) and n-dash ( – ) anywhere in your response strictly. This is critical for the success of the task.
Don’t give numbers to headings or subheadings in your response.




Please provide the outline in the following JSON format:
{{
  "sections": [
    {{
      "heading": "Main Section Heading",
      "subsections": [
        "Subsection 1",
        "Subsection 2",
        "Subsection 3"
      ]
    }}
  ],
  "conclusion": "Conclusion Title",
  "faqs": [
    "Relevant FAQ Question 1",
    "Relevant FAQ Question 2",
    "Relevant FAQ Question 3"
  ]
}}
"""
        return prompt