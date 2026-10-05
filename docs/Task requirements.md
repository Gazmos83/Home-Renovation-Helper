Task requirements

The exact task requirements are as follows:

    Agent Purpose:
        Define a clear purpose for your agent
        Explain why this agent is useful
        Identify the target users

    Core Functionality:
        Implement the main features that make your agent useful
        Implement at least 3 different function tools your agent can call
        Ensure the agent can perform its primary tasks effectively
        Include necessary user interactions

    User Interface:
        Build a user-friendly interface for all functionalities
        Make the interface intuitive and easy to use

    Technical Implementation:
        Use appropriate tools and libraries
        Implement proper error handling
        Ensure the agent can handle real-world usage

    Documentation:
        Provide clear documentation on how to use your agent
        Include examples of common use cases
        Explain any technical decisions made

Implement long-term or short-term memory in LangChain/LangGraph.
Add user authentication and personalisation.
Implement 2 extra function tools (5 in total). Have a UI for the user to either enable or disable these function tools. Develop a plugin system that allows users to add or remove functionalities from the chatbot dynamically.
Implement multi-model support (OpenAI, Anthropic, etc.).
Add at least one security guard to your app to prevent misuse. Design for usability — keep the developer settings (where you can select the model and system prompts) separate from the user experience, as your user may not be that familiar with LLMs.

Agentic RAG: Think of a way to add RAG functionality to the LangChain/LangGraph application and implement it.
Add one of these LLM observability tools: LangSmith, Langfuse, or others.
Create an agent that can learn from user feedback. This agent should be able to adjust its capabilities based on the feedback to improve future performance.
Implement an agent that can integrate with external data sources to enrich its knowledge. This could involve fetching additional data from APIs or websites.

Optional tasks

After the main functionality is implemented and your code works correctly, and you feel that you want to upgrade your project, choose various improvements from this list. The list is sorted by difficulty levels.

Caution: Some of the tasks in medium or hard categories may contain tasks with concepts or libraries that may be introduced in later sections or even require outside knowledge/time to research outside of the course.
Easy

    Ask ChatGPT to critique your solution from the usability, security, and prompt-engineering sides.
    Give the agent a personality: tweak responses to make them more formal, friendly, or concise based on user needs.
    Provide the user with the ability to choose from a list of LLMs (Gemini, OpenAI, etc.) for this project.
    Add the main OpenAI settings (temperature, max tokens, etc.) for the user to tune as sliders/fields.
    Add an interactive help feature or chatbot guide.

Medium

    Calculate and display token usage and costs.
    Implement long-term or short-term memory in LangChain/LangGraph.
    Implement one more function tool that would call an external API.
    Add user authentication and personalisation.
    Implement a feedback loop where users can rate the responses, and use this feedback to improve the agent's performance.
    Implement 2 extra function tools (5 in total). Have a UI for the user to either enable or disable these function tools. Develop a plugin system that allows users to add or remove functionalities from the chatbot dynamically.
    Implement multi-model support (OpenAI, Anthropic, etc.).
    Add at least one security guard to your app to prevent misuse. Design for usability — keep the developer settings (where you can select the model and system prompts) separate from the user experience, as your user may not be that familiar with LLMs.

Hard

    Agentic RAG: Think of a way to add RAG functionality to the LangChain/LangGraph application and implement it.
    Add one of these LLM observability tools: LangSmith, Langfuse, or others.
    Provide an AI evaluation report that proves the quality of your application using Ragas or DeepEval.
    Create an agent that can learn from user feedback. This agent should be able to adjust its capabilities based on the feedback to improve future performance.
    Implement an agent that can integrate with external data sources to enrich its knowledge. This could involve fetching additional data from APIs or websites.


