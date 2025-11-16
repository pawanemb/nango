from typing import Dict, List, Optional
from datetime import datetime
import logging
import os
import json

from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging_config import logger
from app.models.project import Project
from app.db.session import get_db_session
from fastapi import HTTPException
from app.utils.token_tracking import TokenTracker
from app.core.prompt_config import PromptType
from app.services.country_service import CountryService
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService

class TitleGenerationService:
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None, 
                 database_uri: Optional[str] = None):
        """
        Initialize TitleGenerationService.
        
        :param db: Database session
        :param user_id: User ID for tracking
        :param project_id: Project ID for tracking
        :param openai_api_key: OpenAI API key. If not provided, uses settings.
        :param database_uri: Optional database URI. If not provided, tries to get from settings or environment.
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.openai_client = OpenAI(
            api_key=openai_api_key or getattr(settings, 'OPENAI_API_KEY', 
                                              os.getenv('OPENAI_API_KEY'))
        )
        self.logger = logger
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        # Database URI fallback mechanism
        if database_uri:
            self.database_uri = database_uri
        else:
            # Try multiple ways to get database URI
            self.database_uri = (
                getattr(settings, 'SQLALCHEMY_DATABASE_URI', None) or
                os.getenv('DATABASE_URL') or
                'postgresql://localhost/your_database'  # Fallback default
            )

    def generate_title_prompt(
        self,
        primary_keyword: str,
        intent: str,
        category: str,
        country: str,
        subcategory: str,
        secondary_keywords: Optional[List[str]] = None,
        industry: str = "general",
        target_audience: str = "general audience",
        project: Optional[object] = None,
        target_gender: str = "general audience"
    ) -> str:
        """
        Generate prompt for creating blog titles.
        
        :param primary_keyword: Primary keyword for title generation
        :param intent: Search intent (Informational, Navigational, etc.)
        :param category: Blog post category
        :param subcategory: Blog post subcategory
        :param secondary_keywords: Optional list of secondary keywords
        :param industry: Industry context
        :param target_audience: Target audience description
        :return: Formatted prompt string
        """
        secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else ""
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Convert country code to full country name
        try:
            # Check if country is already a full name or a 2-letter code
            if len(country) == 2 and country.isalpha():
                # It's a country code, convert to full name
                country_name = CountryService.get_country_name(country)
                logger.info(f"Converted country code '{country}' to '{country_name}'")
            else:
                # It's already a full country name
                country_name = country
                logger.info(f"Using provided country name: '{country_name}'")
        except ValueError as e:
            # If conversion fails, use the original input and log warning
            logger.warning(f"Country code conversion failed for '{country}': {str(e)}. Using original input.")
            country_name = country
        
        # Check if project is a dictionary or SQLAlchemy model and access languages accordingly
        if project:
            if isinstance(project, dict):
                # If project is a dictionary, use get method
                language = ', '.join(project.get('languages', []))
            else:
                # If project is a SQLAlchemy model, access the languages attribute directly
                language = ', '.join(project.languages) if hasattr(project, 'languages') and project.languages else 'English (UK)'
        else:
            language = 'English (UK)'
        prompt = f"""
   Role:
Act as an SEO expert specializing in writing SEO-friendly content pieces and well-versed with the concepts of keywords and SEO-friendly blog titles. Based on the inputs, goals, and process mentioned below, suggest apt titles that are engaging and SEO-friendly.  

Inputs:
Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords_str}
Category: {category}
Subcategory: {subcategory}
Keyword Location Country: {country_name}
Target Audience: {target_audience}
Language Preference: {language}
Target Gender: {target_gender}
Current Date: {current_date}
IMPORTANT: Your response MUST be a valid JSON object in this exact format:
{{
  "titles": [
    "Title 1",
    "Title 2",
    "Title 3"
  ]
}}

Goals:
Audience-focused: You need to first understand the audience and create content that matches their interest and need for reading the blog. By understanding the audience, you will know about the persona. Also, you will have a better context about the ideas and level of explanations to give for any heading or sub-heading. Writing for a persona in mind makes the blog more engaging and chatty. A good blog always puts its users on the focus and resonates with them on a personal level.  This will ensure that you don’t include abstract, vague, and ambiguous elements in your writing. 

Grab Attention: A strong blog title should immediately capture the reader’s interest. It should be effective and spark curiosity, making the audience eager to click and read more. Attention-grabbing titles often use power words, numbers, questions, or intriguing statements.

Provide Value: The title should clearly communicate the benefit of reading the blog. Readers should instantly understand what they will gain—whether it’s a solution to a problem, valuable insights, actionable tips etc.

 Be Clear and Concise: The title should be short, to the point, and easy to understand. Avoid using overly complex or vague titles may confuse readers or fail to communicate the blog’s purpose effectively. Ideally, a title should be within 65 characters. This ensures that it displays well in search results.

Understanding the primary keyword for focus: The primary keyword will be the main focus of the blog generation. You must understand it to give the relevant blog title that naturally positions it strongly in the blog title.  

 Alignment with the primary keyword intent: Understand the intent of the primary keyword to give the title matching with it. This is crucial for understanding the user’s intent for searching this blog on search engines. Doing this will hence ensure that the users click on this blog title and search engines favor it in their ranking.  Process the following information about the keyword intent to make alignment:
Informational: The keyword indicates the user is seeking information or answers to a specific question. Example: 'How to apply for a visa.'
Navigational: The keyword suggests the user is trying to find a specific website, brand, or entity. Example: 'Facebook login.'
Transactional: The keyword shows the user intends to perform a specific action, such as making a purchase or signing up for a service. Example: 'Buy iPhone 14 online.'
Commercial: The keyword reflects pre-purchase research where the user is comparing products, services, or brands. Example: 'Best laptops under $1000.'

Understand Secondary Keywords: Understand the secondary keywords to understand the context in which the information of the primary keyword has to be covered. For example, for the primary keyword ‘email marketing benefits’, the secondary keyword ‘automation in email marketing’, establishes the need for highlighting the benefits of email marketing and gives a special emphasis on ‘automation’, as one of the benefits of email marketing. You must hence process them to include them in the title wherever possible naturally with the primary keyword. While doing this, you must ensure that the primary focus stays on the primary keyword.

Include Keywords Strategically: You must not include the primary or the secondary keywords of the blog for the sake of it. Incorporate them naturally, conveying the idea of the blog. The primary keyword should align with search intent and be positioned toward the beginning of the title for optimal impact if possible. 

Provide Value: The title should clearly communicate what the reader will gain by clicking on the blog. It should answer the question: “Why should I read this?” For example, instead of "Morning Routine Ideas", use "How a 5-Minute Morning Routine Can Boost Your Productivity All Day".

Alignment with the blog category: Take the reference of the sub-categories explanation corresponding to their respective category to give the title which is best suited for the users. 

Be unique and include fresh perspectives: Don’t give generic or cliched blog titles that do not offer any additional value to readers from what is already easily available to them. Take a fresh angle while making sure that the user intent is prioritised. 

Understand Language Preference: Understand the language preference of the blog text between English (UK) and English (USA). You must write the blog content based on this only. For example, if the user has selected English (UK) as their language preference, then words like 'recognize' must be written as 'recognise' to support the preference.

Use simplified language: The tonality of the section content must be direct and must avoid unnecessary complex wordings. Replace complex phrases with simpler alternatives to improve relatability. Here are a few examples of that: 

In order to → To; Despite the fact that → Although; Leverage → Use; Utilize → Use, Subsequent → Next, following; Commence → Start, begin; Terminate → End, stop; Ascertain → Find out, determine; Facilitate → Help, ease, enable; Expedite → Speed up, accelerate; Implement → Carry out, apply, put in place; Disseminate → Share, spread; Mitigate → Reduce, lessen, ease; Enumerate → List, count; Comprehend → Understand, grasp; Obtain → Get; Procure → Get, acquire; Endeavor → Try, attempt; Illustrate → Show, explain; Indicate → Show, point out; Demonstrate → Show, prove; Substantial → Large, significant; Adequate → Enough, sufficient; Pertinent → Relevant, related; Consolidate → Combine, merge; Constitute → Make up, form; Rectify → Fix, correct; Optimize → Improve, make better; Articulate → Express, explain; Negate → Cancel, undo; Presume → Suppose, assume; Attain → Reach, achieve; Allocate → Give, assign; Engage in → Take part in, do; Accomplish → Complete, achieve; Contemplate → Think about, consider; Scrutinize → Examine, check; Advocate → Support, recommend; Enhance → Improve, boost; Elicit → Draw out, bring out

Include Keywords Strategically: Incorporating relevant keywords helps improve search engine rankings. However, the placement should feel natural rather than forced. The primary keyword should align with search intent and be positioned toward the beginning of the title for optimal impact.

Maintain clarity and conciseness: Keep the titles short and engaging. The ideal length of SEO friendly blog title is less than 65 characters, clearly telling what the blog title is about. 
Steps 
Step 1, Understand the primary keyword and its intent: Understand the primary keyword and the intent to know about the type of blog the users can create. Give title suggestions based on this such that it makes absolute sense why any category or sub-category has been suggested for the selected primary keyword.

Step 2, Understand the secondary keyword, industry, and target audience for a better context: Understand the information about the secondary keywords, industry, and target audience to know about the context in which the blog title with the selected primary keyword will be created. 

Step 3, Understand blog category and sub-category: Take the reference of all the sub-category explanations corresponding to their category to give the most suitable title suggestions:


Action-Oriented 

How-To Guides
Explanation: Step-by-step instructions for completing a task or solving a problem.
Suitability: Ideal for beginners and DIY enthusiasts.
Pros: Practical, easy to follow.
Cons: Can feel overdone if not unique.
Tips: Use numbered steps and visuals.
Examples: How to Design a Professional Logo in 10 Steps.

Steps
Explanation: Breaks down a process into small, manageable parts.
Suitability: Great for task-oriented readers.
Pros: Simple and actionable.
Cons: May oversimplify complex tasks.
Tips: Include sub-steps where necessary.
Examples: 5 Steps to Master Public Speaking.

Process
Explanation: Explains the methodology for completing a task.
Suitability: Ideal for technical or professional audiences.
Pros: Provides clarity on workflows.
Cons: May feel dry without visuals.
Tips: Add flowcharts or diagrams.
Examples: The Process of Building a Solar Panel.

Checklist
Explanation: A list of items or tasks to complete.
Suitability: Perfect for planners or project managers.
Pros: Easy to reference.
Cons: Lacks depth in explanations.
Tips: Organize items logically.
Examples: Checklist for Launching a New Product.

Guide
Explanation: Comprehensive walkthrough of a topic.
Suitability: Ideal for complex subjects.
Pros: Provides in-depth understanding.
Cons: Requires significant research.
Tips: Structure content with headings and subheadings.
Examples: A Guide to Investing in Real Estate.

Avoiding Mistakes
Explanation: Highlights common pitfalls and how to avoid them.
Suitability: Great for beginners.
Pros: Builds trust by showcasing expertise.
Cons: Can be overly negative if not balanced.
Tips: Pair mistakes with solutions.
Examples: Mistakes to Avoid When Starting a Business.

Overcoming Challenges
Explanation: Offers strategies to tackle specific difficulties.
Suitability: Perfect for problem-solving audiences.
Pros: Engages readers seeking solutions.
Cons: Requires detailed research.
Tips: Use real-life examples.
Examples: How to Overcome Writer’s Block.

Do’s & Don’ts
Explanation: Outlines best practices and actions to avoid.
Suitability: Ideal for quick-reference content.
Pros: Straightforward and actionable.
Cons: Can feel overly simplistic.
Tips: Balance do’s with equal don’ts.
Examples: Do’s and Don’ts of Email Marketing.

Implementation Plans
Explanation: A structured plan for applying a concept.
Suitability: Best for organizational audiences.
Pros: Encourages action.
Cons: Requires detailed knowledge of the topic.
Tips: Include timelines or milestones.
Examples: Implementation Plan for Agile Project Management.

Quick Wins
Explanation: Small, actionable tips that provide immediate results.
Suitability: Perfect for time-strapped readers.
Pros: Highly shareable.
Cons: May lack depth.
Tips: Focus on tips that are universally applicable.
Examples: 5 Quick Wins to Improve Website Speed.

Fast-Track Methods
Explanation: Simplified methods to achieve goals faster.
Suitability: Ideal for readers seeking efficiency.
Pros: Appeals to busy professionals.
Cons: Risk of oversimplification.
Tips: Ensure credibility by backing up claims.
Examples: Fast-Track Method to Learn a New Language in 30 Days.

Best Ways
Explanation: Lists the most effective methods for achieving results.
Suitability: Useful for practical readers.
Pros: Encourages comparison of approaches.
Cons: May seem opinionated if not backed by data.
Tips: Support with evidence or expert opinions.
Examples: The Best Ways to Save Money on Groceries.

Shortcuts
Explanation: Easy hacks to simplify tasks.
Suitability: Appeals to time-conscious readers.
Pros: Highly engaging.
Cons: May oversimplify important details.
Tips: Include disclaimers where applicable.
Examples: Shortcuts for Creating Engaging PowerPoint Presentations.

 Explanatory 

What
Explanation: Defines a concept or term.
Suitability: Best for beginners.
Pros: Builds foundational knowledge.
Cons: Lacks actionability.
Tips: Include practical examples.
Examples: What Is Quantum Computing?

Why
Explanation: Explains the significance of a topic.
Suitability: Great for engaging curious readers.
Pros: Provides context.
Cons: May lack actionable insights.
Tips: Add data to support arguments.
Examples: Why Electric Cars Are the Future of Transportation.

Explainer
Explanation: Breaks down a complex topic into simple terms.
Suitability: Ideal for industries like tech or finance.
Pros: Builds credibility.
Cons: Requires expertise.
Tips: Use analogies.
Examples: Explainer: The Basics of Blockchain Technology.

Overview
Explanation: Provides a broad understanding of a topic.
Suitability: Perfect for introductory-level readers.
Pros: Easy to follow.
Cons: Lacks depth.
Tips: Use a clear structure.
Examples: An Overview of Renewable Energy Sources.

Examples
Explanation: Offers illustrations to clarify concepts.
Suitability: Great for practical topics.
Pros: Engaging and relatable.
Cons: Can feel repetitive.
Tips: Use diverse examples.
Examples: Examples of Effective Marketing Campaigns.

Importance
Explanation: Highlights the value of a topic.
Suitability: Best for advocacy or awareness campaigns.
Pros: Drives emotional engagement.
Cons: May feel promotional.
Tips: Use case studies for credibility.
Examples: The Importance of Cybersecurity in Small Businesses.

What Is/Definition
Explanation: Focuses on defining terms or concepts.
Suitability: Beginner-friendly.
Pros: Provides clarity.
Cons: Can feel basic for advanced readers.
Tips: Add related terms or FAQs.
Examples: What Is Artificial Intelligence?

Behind the Scenes
Explanation: Reveals the internal workings of a concept or event.
Suitability: Perfect for storytelling.
Pros: Highly engaging.
Cons: Limited actionability.
Tips: Use visuals.
Examples: Behind the Scenes of a Netflix Production.

Clarifications
Explanation: Explains confusing or misunderstood topics.
Suitability: Best for educational content.
Pros: Builds trust.
Cons: Can feel pedantic.
Tips: Focus on common misconceptions.
Examples: Clarifying the Difference Between Bitcoin and Blockchain.

Debunking Concepts
Explanation: Challenges myths or misconceptions.
Suitability: Great for industries with common myths.
Pros: Builds credibility.
Cons: Requires strong evidence.
Tips: Include data to support claims.
Examples: Debunking the Myth: Organic Food Is Always Healthier.

Simplified Overviews
Explanation: Provides an easy-to-digest summary.
Suitability: Best for introductory audiences.
Pros: Accessible and engaging.
Cons: May lack depth for advanced readers.
Tips: Focus on clarity.
Examples: Simplified Overview of Climate Change.

Comparative 

Vs
Explanation: Direct comparison between two options, highlighting strengths and weaknesses.
Suitability: Ideal for product or service comparisons, decision-making guides.
Pros: Highly engaging, helps readers make informed decisions.
Cons: Risk of bias if not balanced.
Tips: Clearly highlight key differentiators with a conclusion.
Examples: iPhone vs. Android: Which Is Better for Creatives?

Comparison
Explanation: Explores similarities and differences between multiple options.
Suitability: Great for audience segments making choices.
Pros: Useful for decision-making.
Cons: Can feel repetitive without clear distinctions.
Tips: Use charts or tables for easy comparison.
Examples: Comparison of Freelancing Platforms: Upwork, Fiverr, and Toptal.

Difference
Explanation: Focuses on differentiating two or more related concepts.
Suitability: Perfect for industries with confusing terminology or options.
Pros: Adds clarity to complex subjects.
Cons: Limited appeal if the differences are minor.
Tips: Focus on key points of divergence.
Examples: Difference Between AI and Machine Learning.

Best
Explanation: Highlights the top choice based on specific criteria.
Suitability: Ideal for rankings or recommendations.
Pros: Encourages trust and authority.
Cons: May seem subjective without data support.
Tips: Clearly state evaluation criteria.
Examples: The Best Travel Destinations for Adventure Seekers.

Pros and Cons
Explanation: Weighs the advantages and disadvantages of a topic.
Suitability: Perfect for decision-making content.
Pros: Balanced and informative.
Cons: May lack actionable conclusions.
Tips: End with a summary of the key takeaways.
Examples: The Pros and Cons of Remote Work.

Alternative Options
Explanation: Suggests viable alternatives to a commonly known option.
Suitability: Ideal for audiences looking for more variety.
Pros: Encourages exploration of lesser-known options.
Cons: May require extensive research.
Tips: Highlight the unique features of each alternative.
Examples: 5 Alternative Platforms to Zoom for Video Conferencing.

Which Is Better
Explanation: Helps readers choose between two competing options.
Suitability: Great for consumer-focused industries.
Pros: Encourages engagement through comparisons.
Cons: Can feel opinionated without solid evidence.
Tips: Use data and case studies for credibility.
Examples: Which Is Better: Investing in Stocks or Real Estate?

Head-to-Head Comparisons
Explanation: Directly compares two products, services, or ideas side-by-side.
Suitability: Best for B2B or product-focused industries.
Pros: Engages readers seeking clarity.
Cons: Limited appeal if the comparison isn’t meaningful.
Tips: Use visuals like comparison tables.
Examples: Head-to-Head Comparison of Canva vs. Adobe Spark.

Choosing the Right Option
Explanation: Guides readers on selecting the best choice based on their needs.
Suitability: Ideal for decision-making content.
Pros: Highly actionable.
Cons: May lack depth without real-life examples.
Tips: Include pros and cons for each option.
Examples: How to Choose the Right Laptop for Work or Gaming.

Strategic and Analytical 

Strategies
Explanation: Provides actionable plans to achieve a specific goal.
Suitability: Perfect for professional and industry-focused audiences.
Pros: Adds depth and credibility.
Cons: Requires detailed knowledge of the topic.
Tips: Break down strategies into clear steps.
Examples: 5 Marketing Strategies for SaaS Companies.

Techniques
Explanation: Focuses on methods or skills to improve performance.
Suitability: Best for how-to or self-improvement content.
Pros: Practical and implementable.
Cons: May feel redundant without unique insights.
Tips: Include specific examples or applications.
Examples: Techniques for Writing Engaging Blog Content.

Mastering
Explanation: Helps readers become experts in a specific skill or field.
Suitability: Ideal for professional development.
Pros: Positions the writer as an authority.
Cons: Limited appeal to beginners.
Tips: Use advanced tips and expert advice.
Examples: Mastering Public Speaking for Business Professionals.

Principles
Explanation: Outlines fundamental rules or values for success.
Suitability: Best for leadership or motivational topics.
Pros: Engages audiences seeking foundational insights.
Cons: May lack actionable steps.
Tips: Use real-world examples to illustrate principles.
Examples: The Principles of Effective Time Management.

Best Practices
Explanation: Provides tried-and-true methods for achieving success.
Suitability: Great for industries with established norms.
Pros: Builds trust and authority.
Cons: May lack innovation.
Tips: Back up practices with data or testimonials.
Examples: Best Practices for Conducting Virtual Meetings.

Secrets
Explanation: Reveals lesser-known insights or tips.
Suitability: Perfect for intriguing and shareable content.
Pros: Creates curiosity and engagement.
Cons: Can feel clickbaity if not valuable.
Tips: Deliver real value, not fluff.
Examples: The Secrets to Successful Social Media Marketing.

Blueprints
Explanation: A comprehensive framework for success.
Suitability: Ideal for business or personal growth topics.
Pros: Provides a clear roadmap.
Cons: Time-intensive to create.
Tips: Include actionable steps and visuals.
Examples: Blueprint for Scaling a Startup in 2024.

Game Plans
Explanation: A detailed plan for achieving short-term objectives.
Suitability: Best for task-focused industries.
Pros: Highly actionable.
Cons: May feel narrow in focus.
Tips: Ensure it’s adaptable to different scenarios.
Examples: Game Plan for Winning Your Next Marketing Campaign.

Tactical Approaches
Explanation: Focuses on specific, on-the-ground actions.
Suitability: Great for hands-on professionals.
Pros: Practical and easy to implement.
Cons: Can lack strategic depth.
Tips: Pair tactical advice with long-term strategies.
Examples: Tactical Approaches for Boosting Website Traffic.

Roadmaps
Explanation: Visualizes a step-by-step journey to a goal.
Suitability: Ideal for long-term planning content.
Pros: Encourages structured action.
Cons: Can feel overwhelming without clear milestones.
Tips: Include stages or phases for clarity.
Examples: Roadmap to Becoming a Data Scientist.

Action Plans
Explanation: Details specific actions needed to achieve a goal.
Suitability: Great for goal-oriented audiences.
Pros: Highly actionable.
Cons: May lack flexibility.
Tips: Provide options for different scenarios.
Examples: Action Plan for Tackling Climate Change.

 Predictive 

Trends
Explanation: Highlights emerging patterns or behaviors in a specific field or industry.
Suitability: Perfect for fast-changing industries like tech, fashion, and marketing.
Pros: Attracts forward-thinking readers and shares.
Cons: Can quickly become outdated.
Tips: Use recent data and expert opinions.
Examples: Top Trends in Artificial Intelligence for 2024.

Prediction
Explanation: Forecasts future developments or outcomes based on current trends.
Suitability: Ideal for thought leadership and strategic content.
Pros: Positions you as an industry visionary.
Cons: Risk of inaccuracy without supporting data.
Tips: Acknowledge uncertainties and provide evidence.
Examples: Predictions for the Future of Remote Work by 2030.

Future
Explanation: Envisions what lies ahead for industries, technologies, or behaviors.
Suitability: Appeals to innovative and curious audiences.
Pros: Engages readers looking for inspiration.
Cons: Can feel speculative without concrete data.
Tips: Focus on plausible scenarios.
Examples: The Future of Electric Vehicles in Urban Areas.

Evaluative

Opportunities
Explanation: Explores untapped areas or niches for growth and innovation.
Suitability: Best for business and entrepreneurial content.
Pros: Encourages actionable insights.
Cons: Requires deep research to identify meaningful opportunities.
Tips: Highlight specific steps to capitalize on opportunities.
Examples: Opportunities for Startups in the Renewable Energy Sector.

Risks
Explanation: Analyzes potential challenges or threats in a field or decision.
Suitability: Great for industries dealing with uncertainties, like finance or tech.
Pros: Builds trust by showcasing expertise in risk management.
Cons: Can discourage action without solutions.
Tips: Pair risks with mitigation strategies.
Examples: Risks of Investing in Cryptocurrency in 2024.

Innovation
Explanation: Discusses groundbreaking developments or technologies.
Suitability: Ideal for tech, healthcare, and design industries.
Pros: Highlights cutting-edge ideas.
Cons: May not appeal to traditionalists.
Tips: Include examples of real-world applications.
Examples: Innovations in 3D Printing for the Construction Industry.

Evolution
Explanation: Tracks changes and growth over time in a concept or industry.
Suitability: Great for historical analysis or thought leadership.
Pros: Provides context and depth.
Cons: Can feel outdated if overly retrospective.
Tips: Connect past trends to present opportunities.
Examples: The Evolution of Social Media Platforms.

Review
Explanation: Evaluates the performance or effectiveness of a product, service, or trend.
Suitability: Best for consumer-focused or analytical audiences.
Pros: Builds trust and credibility.
Cons: May seem biased if not balanced.
Tips: Include both strengths and weaknesses.
Examples: Review of the Latest iPhone Features.

Disruptive Technologies
Explanation: Highlights technologies that significantly change industries.
Suitability: Great for tech-savvy audiences.
Pros: Captures attention with innovation-focused content.
Cons: Requires deep understanding of the technology.
Tips: Include real-world examples and case studies.
Examples: How Blockchain Is Disrupting the Financial Sector.

Market Shifts
Explanation: Examines changes in consumer behavior or industry dynamics.
Suitability: Ideal for business and marketing audiences.
Pros: Offers actionable insights for businesses.
Cons: Requires access to credible data.
Tips: Use visuals like charts to illustrate shifts.
Examples: Market Shifts in E-Commerce Post-Pandemic.

Consumer Behavior Changes
Explanation: Analyzes evolving customer preferences and habits.
Suitability: Perfect for marketers and business strategists.
Pros: Helps businesses adapt to new trends.
Cons: Needs current and reliable data.
Tips: Include data-backed insights and examples.
Examples: How Gen Z Is Redefining Brand Loyalty.

Benefit-Focused 

Benefits/Advantages
Explanation: Highlights the positive aspects of a product, service, or concept.
Suitability: Best for promotional or informational content.
Pros: Persuasive and shareable.
Cons: May seem biased without evidence.
Tips: Pair benefits with examples or data.
Examples: The Benefits of Meditation for Stress Management.

Advantages/Disadvantages
Explanation: Balances the pros and cons of a topic.
Suitability: Ideal for comparative or evaluative content.
Pros: Offers a balanced perspective.
Cons: Requires careful neutrality to avoid bias.
Tips: Use clear headings for each side.
Examples: Advantages and Disadvantages of Cloud Storage.

Features
Explanation: Highlights the attributes or characteristics of a product or service.
Suitability: Great for product marketing or tutorials.
Pros: Engages potential buyers.
Cons: Lacks depth if not contextualized.
Tips: Focus on unique or standout features.
Examples: Top Features of the Latest Tesla Model.

Impact
Explanation: Explores the influence or effects of a topic.
Suitability: Perfect for thought-provoking or advocacy content.
Pros: Adds depth and relatability.
Cons: Can feel abstract without specific examples.
Tips: Use data to demonstrate impact.
Examples: The Impact of Remote Work on Employee Productivity.

Projections
Explanation: Forecasts expected benefits or outcomes of a trend or technology.
Suitability: Best for forward-looking audiences.
Pros: Encourages visionary thinking.
Cons: Risk of overpromising if predictions don’t materialize.
Tips: Ground projections in credible research.
Examples: Projections for Renewable Energy Adoption by 2050.

Future Scenarios
Explanation: Imagines possible outcomes based on current trends.
Suitability: Great for speculative or thought leadership content.
Pros: Engages futurists and innovators.
Cons: Can feel too speculative without grounding.
Tips: Acknowledge uncertainties.
Examples: Future Scenarios for AI in Education.

Biggest Risks
Explanation: Identifies potential threats to a concept or industry.
Suitability: Perfect for risk management and strategic audiences.
Pros: Builds credibility in assessing risks.
Cons: Can deter readers if overly negative.
Tips: Pair risks with potential solutions.
Examples: Biggest Risks in Cryptocurrency Investment.

Lessons from the Past
Explanation: Highlights key learnings from historical events or trends.
Suitability: Great for analytical or reflective content.
Pros: Provides depth and historical context.
Cons: May feel outdated if not connected to current issues.
Tips: Relate past lessons to present challenges.
Examples: Lessons from the 2008 Financial Crisis.

Key Takeaways
Explanation: Summarizes the most important points from an event, study, or trend.
Suitability: Best for busy readers seeking concise information.
Pros: Easy to consume.
Cons: Lacks detail for in-depth analysis.
Tips: Use bullet points for clarity.
Examples: Key Takeaways from the Latest Tech Conference.

Hidden Benefits
Explanation: Uncovers lesser-known advantages of a product, service, or trend.
Suitability: Appeals to curious readers.
Pros: Engaging and insightful.
Cons: Requires thorough research.
Tips: Include specific examples to build credibility.
Examples: Hidden Benefits of Switching to Solar Power.

Transformational Benefits
Explanation: Focuses on how a product, service, or concept can significantly change or improve a situation, behavior, or outcome.
Suitability: Perfect for content targeting industries like personal development, fitness, health, technology, or education, where transformation is a key motivator.
Pros:
Captures emotional engagement by focusing on dramatic outcomes.
Builds trust and credibility by showcasing impactful results.
Highly persuasive for audiences seeking meaningful change.
Cons:
Can feel exaggerated or overly promotional if not backed by evidence.
Requires clear examples to make the transformation relatable.
Tips:
Use case studies or testimonials to demonstrate transformations.
Pair before-and-after comparisons with data or stories.
Highlight tangible and intangible impacts.
Examples:
How AI is Driving Transformational Benefits in Healthcare.
The Transformational Benefits of Practicing Gratitude Daily.
Transformational Benefits of Switching to Renewable Energy.

Unexpected Advantages
Explanation: Highlights lesser-known or surprising benefits of a product, service, or concept that might not be immediately obvious.
Suitability: Best for industries or products with unique features that go beyond their primary purpose, such as lifestyle, technology, or wellness.
Pros:
Sparks curiosity and engagement with readers.
Differentiates the product or concept from competitors.
Provides additional reasons for readers to take interest or action.
Cons:
May seem trivial if the advantage isn’t compelling.
Requires thorough research to uncover truly unexpected benefits.
Tips:
Choose benefits that resonate with the target audience’s values or needs.
Explain why these advantages are often overlooked or underestimated.
Use storytelling or real-life examples to make the benefits relatable.
Examples:
Unexpected Advantages of Walking Meetings for Team Productivity.
5 Surprising Benefits of Drinking Coffee Before a Workout.
The Unexpected Advantages of Using Blockchain Beyond Cryptocurrencies.

Unique Selling Points (USPs)
Explanation: Emphasizes the distinct features or qualities that set a product, service, or idea apart from its competitors.
Suitability: Ideal for marketing content, product pages, or competitive industries like e-commerce, tech, and services.
Pros:
Directly communicates value and differentiation.
Enhances brand positioning in a competitive market.
Encourages conversions by showcasing unique features.
Cons:
Can feel overly promotional if not balanced.
Requires a clear understanding of competitors to avoid generic claims.
Tips:
Focus on features that genuinely add value to the audience.
Avoid vague or unsubstantiated claims like “the best.”
Provide evidence or testimonials to validate USPs.
Examples:
Why Our Software’s AI-Powered Insights Are a Game-Changer for Marketers.
Unique Selling Points of the Tesla Model S: Range, Speed, and Innovation.
Top 3 USPs That Make Our Eco-Friendly Packaging Stand Out.

Inspirational and Creative Buckets

Inspiration
Explanation: Motivates readers through uplifting stories or ideas.
Suitability: Perfect for lifestyle, personal development, or leadership topics.
Pros: Highly shareable and emotionally engaging.
Cons: May lack actionable insights.
Tips: Include relatable elements to connect with the audience.
Examples: Inspiration from Entrepreneurs Who Started with Zero Capital.

Ideas
Explanation: Sparks creativity by suggesting innovative or actionable concepts.
Suitability: Great for brainstorming and out-of-the-box content.
Pros: Encourages engagement and discussions.
Cons: May not suit audiences looking for concrete solutions.
Tips: Add visuals to make ideas more tangible.
Examples: 10 Creative Ideas for Sustainable Packaging.

Journey
Explanation: Chronicles the path of a person, organization, or concept.
Suitability: Ideal for storytelling and brand-building.
Pros: Builds emotional connection with the audience.
Cons: Can feel personal and niche-specific.
Tips: Highlight key milestones and lessons learned.
Examples: The Journey of SpaceX: From Startup to Mars Exploration.

Motivational Messages
Explanation: Encourages readers to take action or change perspectives.
Suitability: Perfect for self-help or leadership topics.
Pros: Engages readers emotionally.
Cons: May lack depth if not tied to actionable advice.
Tips: Use quotes or anecdotes for impact.
Examples: Motivational Lessons from Elon Musk’s Leadership Style.

Visionary Ideas
Explanation: Discusses bold, forward-thinking concepts that push boundaries.
Suitability: Great for innovation-focused audiences.
Pros: Sparks excitement and curiosity.
Cons: May feel speculative without grounding.
Tips: Base ideas on emerging trends or technologies.
Examples: Visionary Ideas for a Carbon-Neutral Future.

Milestone Journeys
Explanation: Celebrates significant achievements or milestones in a field or journey.
Suitability: Perfect for storytelling and reflective content.
Pros: Builds credibility and relatability.
Cons: Limited appeal if milestones are niche-specific.
Tips: Connect milestones to broader industry trends.
Examples: Milestones in the Development of Electric Cars.

Innovative Concepts
Explanation: Explores unique or groundbreaking ideas.
Suitability: Ideal for tech, design, and creative industries.
Pros: Positions the writer as an innovator.
Cons: Can feel theoretical without practical examples.
Tips: Pair concepts with potential applications.
Examples: Innovative Concepts for AI-Powered Learning Tools.

Breakthrough Stories
Explanation: Highlights significant achievements that changed industries or lives.
Suitability: Great for motivational and thought leadership content.
Pros: Builds inspiration and credibility.
Cons: May seem too niche if not connected to a larger narrative.
Tips: Include quantifiable results or impacts.
Examples: Breakthrough Story: How CRISPR Revolutionized Genetic Engineering.

Educational 

Lessons Learned
Explanation: Shares insights gained from past experiences, projects, or failures.
Suitability: Perfect for leadership, entrepreneurship, or reflective content.
Pros: Engages readers with relatable lessons.
Cons: Can feel redundant if overly personal.
Tips: Focus on universally applicable takeaways.
Examples: Lessons Learned from Scaling a Startup to $1 Million Revenue.

Glossary
Explanation: Provides a list of key terms with definitions for a specific topic or industry.
Suitability: Best for technical or academic content.
Pros: Builds foundational understanding for readers.
Cons: Limited engagement for advanced audiences.
Tips: Include practical examples for complex terms.
Examples: A Glossary of Essential AI Terms for Beginners.

Exploratory
Explanation: Explores a topic in depth, often without concrete conclusions.
Suitability: Ideal for thought-provoking or speculative content.
Pros: Encourages curiosity and engagement.
Cons: May feel incomplete without actionable insights.
Tips: Use open-ended questions to provoke thought.
Examples: Exploratory: The Role of AI in Shaping Creativity.

Beginner’s Guides
Explanation: Introduces foundational concepts for readers new to a subject.
Suitability: Best for attracting a broad, beginner-level audience.
Pros: Highly accessible and easy to understand.
Cons: May lack depth for advanced readers.
Tips: Use simple language and clear structure.
Examples: Beginner’s Guide to Investing in Real Estate.

Intermediate Insights
Explanation: Bridges the gap between beginner and advanced knowledge.
Suitability: Great for readers with some prior experience.
Pros: Adds value to semi-experienced audiences.
Cons: Can feel too broad without focus.
Tips: Provide practical applications for intermediate readers.
Examples: Intermediate Guide to Building a Personal Brand Online.

Advanced Tips
Explanation: Offers expert-level advice for seasoned readers.
Suitability: Ideal for niche or professional audiences.
Pros: Positions the writer as an authority.
Cons: May alienate beginners.
Tips: Include examples and case studies for context.
Examples: Advanced Tips for Optimizing SEO in 2024.

Key Concepts
Explanation: Focuses on fundamental ideas or principles within a topic.
Suitability: Great for educational or introductory content.
Pros: Provides a strong foundation for readers.
Cons: May lack actionability if too abstract.
Tips: Break concepts into sections for clarity.
Examples: Key Concepts in Behavioral Economics.

Must-Know Facts
Explanation: Highlights important or surprising information.
Suitability: Best for engaging and informative content.
Pros: Shareable and easy to read.
Cons: Limited depth if not expanded.
Tips: Use bullet points for clarity.
Examples: 10 Must-Know Facts About the Metaverse.

FAQs Answered
Explanation: Responds to common questions about a topic.
Suitability: Perfect for addressing beginner concerns or misconceptions.
Pros: Highly relevant and reader-focused.
Cons: Can feel repetitive if not well-structured.
Tips: Include a mix of basic and complex questions.
Examples: FAQs About Filing Taxes as a Freelancer.

Audience and Geography-Specific Buckets

Audience-Based
Explanation: Tailors content to a specific demographic or user group.
Suitability: Great for personalized marketing or educational content.
Pros: Builds connection and relatability with the target audience.
Cons: Limited appeal outside the target group.
Tips: Use audience-specific language and examples.
Examples: How Gen Z Is Changing the Workforce.

Geography-Based
Explanation: Focuses on trends, challenges, or opportunities within a specific region.
Suitability: Best for industries with localized markets or global comparisons.
Pros: Enhances relevance for regional readers.
Cons: Limited appeal outside the geography.
Tips: Include local data and case studies.
Examples: Geography-Based Challenges in Sustainable Farming in Asia.

Regional Trends
Explanation: Explores patterns and behaviors unique to a specific area.
Suitability: Perfect for global industries analyzing local markets.
Pros: Highlights cultural and regional differences.
Cons: Requires detailed research.
Tips: Use visuals to compare regional data.
Examples: Emerging E-Commerce Trends in Latin America.

Cultural Perspectives
Explanation: Examines topics through the lens of cultural practices or values.
Suitability: Ideal for global or multicultural audiences.
Pros: Engages readers by highlighting diversity.
Cons: Can feel overly niche if not broadly applicable.
Tips: Include relatable anecdotes or stories.
Examples: How Japanese Culture Influences Leadership Styles.

Demographic-Specific Insights
Explanation: Analyzes behaviors or preferences of a specific age group or demographic.
Suitability: Great for marketers or social researchers.
Pros: Builds targeted appeal.
Cons: Limited reach outside the demographic.
Tips: Use credible data to support claims.
Examples: Demographic Insights: Millennials’ Preferences for Homeownership.

Local Success Stories
Explanation: Highlights achievements within a particular region or community.
Suitability: Perfect for showcasing regional expertise or talent.
Pros: Builds local credibility and inspiration.
Cons: Limited global relevance.
Tips: Use detailed interviews or case studies.
Examples: Local Success Stories of Women Entrepreneurs in India.

Community-Based Content
Explanation: Focuses on collective efforts or issues within a specific community.
Suitability: Ideal for advocacy or grassroots movements.
Pros: Builds emotional connections with readers.
Cons: May feel niche-specific without broad applicability.
Tips: Highlight tangible impacts or outcomes.
Examples: Community-Based Initiatives for Reducing Urban Pollution.

Focused and Problem-Solving Buckets

Problem-Solving
Explanation: Addresses a specific issue and provides actionable solutions.
Suitability: Ideal for troubleshooting, technical, or advisory content.
Pros: Highly engaging for readers actively seeking help.
Cons: Requires a deep understanding of the problem to offer relevant solutions.
Tips: Present solutions step-by-step and include examples.
Examples: How to Solve Common Errors in WordPress Plugins.

Challenges
Explanation: Explores difficulties in a specific field and how to tackle them.
Suitability: Best for industries facing frequent obstacles, such as startups or education.
Pros: Builds trust and credibility by addressing pain points.
Cons: Can feel negative without balancing challenges with solutions.
Tips: Pair each challenge with actionable advice.
Examples: Challenges of Scaling a Remote Team and How to Overcome Them.

Disadvantages
Explanation: Focuses on the drawbacks or downsides of a topic, product, or service.
Suitability: Great for balanced reviews or critical evaluations.
Pros: Adds credibility by addressing both sides of an issue.
Cons: May feel discouraging if solutions aren’t provided.
Tips: Conclude with a positive outlook or alternatives.
Examples: Disadvantages of Freelancing as a Career Path.

Root Cause Analysis
Explanation: Investigates the fundamental reasons behind a problem or failure.
Suitability: Perfect for technical, operational, or management-related audiences.
Pros: Helps readers deeply understand the problem.
Cons: Can feel overly technical for general audiences.
Tips: Include visual diagrams like fishbone charts or flowcharts.
Examples: Root Cause Analysis of High Employee Turnover.

Common Pitfalls
Explanation: Identifies frequent mistakes and how to avoid them.
Suitability: Best for beginner or advisory content.
Pros: Highly relatable and actionable.
Cons: May seem repetitive if not paired with solutions.
Tips: Provide real-world examples to illustrate pitfalls.
Examples: Common Pitfalls in Content Marketing and How to Avoid Them.

Mistakes to Avoid
Explanation: Focuses on errors readers often make and offers preventive advice.
Suitability: Great for practical, how-to-style content.
Pros: Builds authority by helping readers navigate challenges.
Cons: Can feel redundant without unique insights.
Tips: Use a listicle format for clarity.
Examples: Mistakes to Avoid When Launching a Product.

Step-by-Step Resolutions
Explanation: Provides detailed instructions for resolving specific issues.
Suitability: Ideal for troubleshooting and technical audiences.
Pros: Offers clear, actionable guidance.
Cons: Requires thorough knowledge of the topic.
Tips: Use screenshots or visuals for better comprehension.
Examples: Step-by-Step Resolution for Debugging a JavaScript Error.

Real-World Challenges
Explanation: Discusses actual difficulties faced in industries or everyday life.
Suitability: Perfect for relatable or motivational content.
Pros: Engages readers by showcasing authenticity.
Cons: Can feel limited if the challenges are too niche.
Tips: Highlight solutions or outcomes for each challenge.
Examples: Real-World Challenges of Sustainable Urban Development.

Creative and Unique Buckets

Busting Myths
Explanation: Challenges common misconceptions about a topic or industry.
Suitability: Great for thought leadership and educational content.
Pros: Builds credibility and encourages engagement.
Cons: Requires thorough research to refute myths effectively.
Tips: Use data or expert opinions to support your claims.
Examples: Busting Myths About Vegan Diets.

Transformation
Explanation: Highlights how a product, service, or concept has evolved or impacted lives.
Suitability: Perfect for storytelling and advocacy content.
Pros: Inspires readers and showcases progress.
Cons: May feel overly promotional if not balanced.
Tips: Include before-and-after comparisons.
Examples: Transformation of Education Through Online Learning.

Secrets
Explanation: Shares lesser-known tips or information to intrigue readers.
Suitability: Great for listicles or actionable guides.
Pros: Creates curiosity and encourages clicks.
Cons: Can feel clickbaity if not valuable.
Tips: Deliver actionable or surprising insights.
Examples: Secrets to Growing Your Instagram Following Organically.

Hidden Gems
Explanation: Showcases overlooked or underrated options, places, or ideas.
Suitability: Best for travel, lifestyle, or tech content.
Pros: Engages readers by offering unique value.
Cons: Requires thorough research to find truly hidden gems.
Tips: Use detailed descriptions or examples.
Examples: Hidden Gems of Productivity Apps You Should Try.

Unexpected Discoveries
Explanation: Highlights surprising findings or insights in a field.
Suitability: Ideal for research-based or innovative industries.
Pros: Encourages curiosity and engagement.
Cons: Needs credible sources to back claims.
Tips: Use storytelling to make discoveries relatable.
Examples: Unexpected Discoveries in AI Research.

Surprising Truths
Explanation: Reveals facts or insights that challenge conventional wisdom.
Suitability: Perfect for educational or engaging content.
Pros: Sparks interest and discussion.
Cons: Can feel sensationalist if not supported by evidence.
Tips: Provide credible data or case studies.
Examples: Surprising Truths About Work-Life Balance Myths.

Unusual Applications
Explanation: Discusses unconventional ways a product, concept, or technology is used.
Suitability: Best for tech, lifestyle, or creative industries.
Pros: Engages readers by showcasing innovation.
Cons: May feel irrelevant if examples are too niche.
Tips: Use relatable scenarios to explain applications.
Examples: Unusual Applications of AI in Agriculture.

Out-of-the-Box Thinking
Explanation: Encourages creativity by presenting unconventional solutions or ideas.
Suitability: Ideal for brainstorming, marketing, or problem-solving content.
Pros: Differentiates your content from competitors.
Cons: May alienate traditional audiences.
Tips: Include practical steps to implement ideas.
Examples: Out-of-the-Box Marketing Campaigns That Worked.


Output:
The response must only include the generated blog title(s) based on the input provided.
Do not provide any additional comments, explanations, or descriptions.
You must give me at least 10 variations of the title in the output.
Give the output in the json format. 
Do not include ```json in your response. 

Return ONLY a JSON object in this exact format:
{{
  "titles": [
    "Title 1",
    "Title 2",
    "Title 3"
  ]
}}
    """

        return prompt

    def generate_titles(
        self,
        primary_keyword: str,
        intent: str,
        category: str,
        country: str,
        subcategory: str,
        project_id: str,
        secondary_keywords: Optional[List[str]] = None,
        project: Optional[object] = None
    ) -> Dict[str, List[str]]:
        """
        Generate blog titles using OpenAI.
        
        :param primary_keyword: Primary keyword for title generation
        :param intent: Search intent
        :param category: Blog post category
        :param subcategory: Blog post subcategory
        :param project_id: Project identifier
        :param secondary_keywords: Optional list of secondary keywords
        :return: Dictionary of generated titles
        """
        try:
            # Update project_id if provided
            if project_id:
                self.project_id = project_id
                
            # Get project details from database
            project = None
            with get_db_session() as db:
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise ValueError(f"Project not found with id: {project_id}")
            # Join all industries with comma
            industry = ", ".join(project.industries) if project.industries else "general"
            # Use age_groups as target audience
            target_audience = ", ".join(project.age_groups) if project.age_groups else "general audience"
            
            # Generate the prompt
            logger.info(f"=== GENERATING AI PROMPT ===")
            logger.info(f"Prompt Generation Parameters:")
            logger.info(f"  - Primary Keyword: {primary_keyword}")
            logger.info(f"  - Country (Raw Input): {country}")
            logger.info(f"  - Industry: {industry}")
            logger.info(f"  - Target Audience: {target_audience}")
            
            prompt = self.generate_title_prompt(
                primary_keyword=primary_keyword,
                intent=intent,
                category=category,
                country=country,
                subcategory=subcategory,
                secondary_keywords=secondary_keywords,
                industry=industry,
                target_audience=target_audience,
                project=project
            )
            
            logger.info(f"=== FINAL PROMPT GENERATED ===")
            logger.info(f"Prompt Length: {len(prompt)} characters")
            logger.info(f"Prompt Preview (first 500 chars): {prompt[:500]}...")
            
            # Call OpenAI API and capture usage data
            logger.info(f"=== CALLING OPENAI API ===")
            logger.info(f"OpenAI Parameters:")
            logger.info(f"  - Model: {settings.OPENAI_MODEL}")
            logger.info(f"  - Temperature: {settings.OPENAI_TEMPERATURE}")
            logger.info(f"  - Max Tokens: {settings.OPENAI_MAX_TOKENS}")
            logger.info(f"  - System Message: You are an expert SEO content strategist...")
            logger.info(f"  - User Prompt Length: {len(prompt)} characters")
            
            
            response = self.openai_client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": "You are an expert SEO content strategist. Your task is to generate blog titles and return them in a valid JSON format with a 'titles' array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Record LLM usage with billing
            title_metadata = {
                "title_generation": {
                    "primary_keyword": primary_keyword,
                    "intent": intent,
                    "category": category,
                    "country": country,
                    "subcategory": subcategory,
                    "industry": industry
                }
            }
            
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="title_generation",
                model_name=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                service_description="Title generation using OpenAI",
                project_id=self.project_id,
                additional_metadata=title_metadata
            )
            
            self.logger.info(f"✅ Recorded title generation usage: {result}")
            
            logger.info(f"=== OPENAI API RESPONSE RECEIVED ===")
            logger.info(f"Response Model: {response.model}")
            logger.info(f"Response ID: {response.id}")
            if hasattr(response, 'usage') and response.usage:
                logger.info(f"Token Usage - Prompt: {response.usage.input_tokens}, Completion: {response.usage.output_tokens}, Total: {response.usage.total_tokens}")
            
            # Add debug logging
            self.logger.debug("-" * 100)  
            response_content = response.output_text.strip()
            self.logger.debug(f"Raw OpenAI response: {response_content}")
            self.logger.debug("-" * 100)
            
            # Parse the JSON response
            logger.info(f"=== PARSING OPENAI RESPONSE ===")
            logger.info(f"Raw Response Content: {response_content[:200]}...")
            
            try:
                titles_data = json.loads(response_content)
                titles = titles_data.get('titles', [])
                
                logger.info(f"=== TITLES SUCCESSFULLY PARSED ===")
                logger.info(f"Number of titles generated: {len(titles)}")
                for i, title in enumerate(titles, 1):
                    logger.info(f"  {i}. {title}")
                
                result = {"titles": titles}
                logger.info(f"Final Result: {result}")
                return result
                
            except json.JSONDecodeError:
                self.logger.error("Failed to parse titles JSON from OpenAI response")
                raise ValueError("Invalid title generation response")
        
        except Exception as e:
            self.logger.error(f"Error generating titles: {str(e)}")
            raise

    def generate_title_workflow(
        self,
        primary_keyword: str,
        intent: str,
        category: str,
        subcategory: str,
        country: str,
        project_id: str,
        secondary_keywords: Optional[List[str]] = None,
        project: Optional[object] = None
    ) -> Dict[str, List[str]]:
        """
        Complete title generation workflow.
        
        :param primary_keyword: Primary keyword for title generation
        :param intent: Search intent
        :param category: Blog post category
        :param subcategory: Blog post subcategory
        :param project_id: Project identifier
        :param secondary_keywords: Optional list of secondary keywords
        :return: Dictionary of generated titles
        """
        try:
            logger.info(f"=== TITLE GENERATION WORKFLOW STARTED ===")
            logger.info(f"Workflow Parameters:")
            logger.info(f"  - Primary Keyword: {primary_keyword}")
            logger.info(f"  - Intent: {intent}")
            logger.info(f"  - Category: {category}")
            logger.info(f"  - Subcategory: {subcategory}")
            logger.info(f"  - Country (Before Conversion): {country}")
            logger.info(f"  - Secondary Keywords: {secondary_keywords}")
            logger.info(f"  - Project ID: {project_id}")
            
            # Generate titles
            titles_result = self.generate_titles(
                primary_keyword=primary_keyword,
                intent=intent,
                category=category,
                subcategory=subcategory,    
                country=country,
                project_id=project_id,
                secondary_keywords=secondary_keywords,
                project=project
            )
            
            return titles_result
        
        except Exception as e:
            self.logger.error(f"Complete title generation workflow failed: {e}")
            raise
