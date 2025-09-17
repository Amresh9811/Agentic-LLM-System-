import openai
import os
from dotenv import load_dotenv
from collections import deque
from typing import List, Dict, Tuple, Optional
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgenticLLM:
    """
    Lightweight agentic LLM system that processes user input, determines intent,
    and returns appropriate responses using OpenAI's GPT models.
    """
    
    def __init__(self, model: str = "gpt-4o", memory_size: int = 3):
        """
        Initialize the agentic LLM system.
        
        Args:
            model: OpenAI model to use (default: gpt-3.5-turbo)
            memory_size: Number of interactions to keep in memory (default: 3)
        """
        # Load environment variables
        load_dotenv()
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        
        # Memory management - store last N interactions
        self.memory = deque(maxlen=memory_size)
        
        # Intent classification system prompt
        self.intent_system_prompt = """You are an intent classifier. Your job is to classify user input as either 'factual' or 'creative'.

Factual queries include:
- Questions asking for specific information, facts, or data
- Requests for explanations or definitions
- "Who is...", "What is...", "When did...", "How many..." type questions
- Technical or academic questions

Creative prompts include:
- Requests to generate stories, poems, or creative writing
- Requests for captions, taglines, or creative descriptions
- "Write a...", "Create a...", "Generate a..." for creative content
- Brainstorming or imaginative requests

Respond with only 'factual' or 'creative'."""

        # Response generation prompts
        self.factual_system_prompt = """You are a knowledgeable assistant that provides accurate, concise answers to factual questions. 
Focus on being informative, precise, and helpful. Use the conversation context when relevant."""

        self.creative_system_prompt = """You are a creative assistant that generates imaginative and engaging content.
Be creative, original, and engaging while staying appropriate. Use the conversation context when relevant."""

    def _get_context_string(self) -> str:
        """Format conversation memory into a context string."""
        if not self.memory:
            return "No previous conversation."
        
        context_lines = []
        for interaction in self.memory:
            context_lines.append(f"User: {interaction['user_input']}")
            context_lines.append(f"Assistant: {interaction['response']}")
        
        return "\n".join(context_lines[-6:])  # Last 6 lines (3 interactions)

    def _detect_intent(self, user_input: str) -> str:
        """
        Detect whether the input is a factual query or creative prompt.
        
        Args:
            user_input: The user's input text
            
        Returns:
            'factual' or 'creative'
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.intent_system_prompt},
                    {"role": "user", "content": f"Classify this input: '{user_input}'"}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            intent = response.choices[0].message.content.strip().lower()
            
            # Validate response
            if intent not in ['factual', 'creative']:
                logger.warning(f"Unexpected intent classification: {intent}. Defaulting to 'factual'")
                return 'factual'
                
            return intent
            
        except Exception as e:
            logger.error(f"Error in intent detection: {e}")
            return 'factual'  # Safe default

    def _generate_factual_response(self, user_input: str) -> str:
        """
        Generate response for factual queries.
        
        Args:
            user_input: The user's factual question
            
        Returns:
            Factual response string
        """
        context = self._get_context_string()
        
        user_message = f"""Context from previous conversation:
{context}

Current question: {user_input}

Please provide a direct, factual answer."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.factual_system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2,
                max_tokens=250
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating factual response: {e}")
            return f"I apologize, but I encountered an error while processing your question. Please try again."

    def _generate_creative_response(self, user_input: str) -> str:
        """
        Generate response for creative prompts.
        
        Args:
            user_input: The user's creative prompt
            
        Returns:
            Creative response string
        """
        context = self._get_context_string()
        
        user_message = f"""Context from previous conversation:
{context}

Current creative request: {user_input}

Please generate creative content based on this request."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.creative_system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.8,
                max_tokens=250
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating creative response: {e}")
            return f"I apologize, but I encountered an error while generating creative content. Please try again."

    def _store_interaction(self, user_input: str, response: str, intent: str):
        """
        Store interaction in memory.
        
        Args:
            user_input: User's input
            response: Assistant's response
            intent: Detected intent ('factual' or 'creative')
        """
        interaction = {
            'user_input': user_input,
            'response': response,
            'intent': intent,
            'timestamp': time.time()
        }
        self.memory.append(interaction)

    def process_input(self, user_input: str) -> Dict[str, str]:
        """
        Main method to process user input and return appropriate response.
        
        Args:
            user_input: The user's input text
            
        Returns:
            Dictionary containing user_input, intent, and response
        """
        if not user_input or not user_input.strip():
            return {
                'user_input': user_input,
                'intent': 'unknown',
                'response': 'Please provide a valid input.'
            }
        
        user_input = user_input.strip()
        
        # Step 1: Detect intent
        logger.info(f"Processing input: {user_input[:50]}...")
        intent = self._detect_intent(user_input)
        logger.info(f"Detected intent: {intent}")
        
        # Step 2: Generate appropriate response
        if intent == 'creative':
            response = self._generate_creative_response(user_input)
        else:  # factual
            response = self._generate_factual_response(user_input)
        
        # Step 3: Store interaction in memory
        self._store_interaction(user_input, response, intent)
        
        return {
            'user_input': user_input,
            'intent': intent,
            'response': response
        }

    def get_memory_summary(self) -> List[Dict]:
        """Get current memory state."""
        return list(self.memory)

    def clear_memory(self):
        """Clear conversation memory."""
        self.memory.clear()
        logger.info("Memory cleared")

    def get_memory_stats(self) -> Dict:
        """Get statistics about memory usage."""
        if not self.memory:
            return {'total_interactions': 0, 'factual_count': 0, 'creative_count': 0}
        
        factual_count = sum(1 for interaction in self.memory if interaction['intent'] == 'factual')
        creative_count = sum(1 for interaction in self.memory if interaction['intent'] == 'creative')
        
        return {
            'total_interactions': len(self.memory),
            'factual_count': factual_count,
            'creative_count': creative_count,
            'memory_capacity': self.memory.maxlen
        }


def run_comprehensive_tests():
    """Run comprehensive test cases covering various scenarios."""
    print("=== AGENTIC LLM SYSTEM - COMPREHENSIVE TESTING ===\n")
    
    agent = AgenticLLM()
    
    test_cases = [
        # === FACTUAL QUERIES ===
        {
            'category': 'Factual - Basic Facts',
            'inputs': [
                "Who is the CEO of Google?",
                "What is the capital of France?",
                "How many continents are there?",
                "What year was Python programming language created?",
                "What is the speed of light?"
            ]
        },
        {
            'category': 'Factual - Definitions',
            'inputs': [
                "What is machine learning?",
                "Define photosynthesis",
                "What does API stand for?",
                "Explain what blockchain is"
            ]
        },
        {
            'category': 'Factual - Historical',
            'inputs': [
                "When did World War II end?",
                "Who invented the telephone?",
                "What year was the internet created?"
            ]
        },
        
        # === CREATIVE PROMPTS ===
        {
            'category': 'Creative - Captions & Descriptions',
            'inputs': [
                "Give me a caption for a futuristic city",
                "Describe a magical forest in two sentences",
                "Create a tagline for an eco-friendly coffee shop",
                "Write a caption for a sunset over mountains"
            ]
        },
        {
            'category': 'Creative - Stories & Poems',
            'inputs': [
                "Write a short poem about rain",
                "Create a story about a time-traveling cat",
                "Write a haiku about technology",
                "Tell me a story about a robot learning to paint"
            ]
        },
        {
            'category': 'Creative - Brainstorming',
            'inputs': [
                "Generate 3 names for a space exploration company",
                "Create a concept for a mobile app that helps with meditation",
                "Invent a new ice cream flavor and describe it"
            ]
        },
        
        # === EDGE CASES ===
        {
            'category': 'Edge Cases',
            'inputs': [
                "Hello",
                "Help",
                "?",
                "What do you think about AI and creativity?",
                "Can you both explain quantum physics and write a poem about it?"
            ]
        },
        
        # === MEMORY/CONTEXT TESTING ===
        {
            'category': 'Memory & Context Testing',
            'inputs': [
                "Tell me about Albert Einstein",
                "What did he discover?",  # Should reference Einstein
                "When was he born?",     # Should still reference Einstein
                "Now tell me about Marie Curie",
                "What was her most famous discovery?"  # Should reference Curie
            ]
        }
    ]
    
    # Run all test cases
    for test_group in test_cases:
        print(f"\n{'='*60}")
        print(f"TESTING: {test_group['category']}")
        print('='*60)
        
        for i, test_input in enumerate(test_group['inputs'], 1):
            print(f"\nTest {i}: {test_input}")
            print("-" * 40)
            
            result = agent.process_input(test_input)
            print(f"Intent: {result['intent'].upper()}")
            print(f"Response: {result['response']}")
            
            # Brief pause to avoid rate limiting
            time.sleep(0.8)
    
    # Show final memory state and statistics
    print(f"\n{'='*60}")
    print("FINAL MEMORY STATE & STATISTICS")
    print('='*60)
    
    stats = agent.get_memory_stats()
    print(f"Memory Statistics:")
    print(f"  Total interactions: {stats['total_interactions']}")
    print(f"  Factual queries: {stats['factual_count']}")
    print(f"  Creative prompts: {stats['creative_count']}")
    print(f"  Memory capacity: {stats['memory_capacity']}")
    
    print(f"\nLast {len(agent.memory)} interactions in memory:")
    memory = agent.get_memory_summary()
    for i, interaction in enumerate(memory, 1):
        print(f"{i}. [{interaction['intent'].upper()}] {interaction['user_input']}")
        print(f"   → {interaction['response'][:80]}{'...' if len(interaction['response']) > 80 else ''}")


def interactive_mode():
    """Run interactive mode for manual testing and demonstration."""
    print("=== AGENTIC LLM SYSTEM - INTERACTIVE MODE ===")
    print("Commands:")
    print("  'exit' - Quit the program")
    print("  'memory' - Show conversation history")
    print("  'stats' - Show memory statistics")
    print("  'clear' - Clear conversation memory")
    print("  'help' - Show this help message")
    print("\nStart chatting!\n")
    
    agent = AgenticLLM()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            elif user_input.lower() == 'memory':
                memory = agent.get_memory_summary()
                print(f"\n--- Conversation History ({len(memory)} interactions) ---")
                if not memory:
                    print("No interactions yet.")
                else:
                    for i, interaction in enumerate(memory, 1):
                        print(f"{i}. You [{interaction['intent']}]: {interaction['user_input']}")
                        print(f"   Assistant: {interaction['response'][:100]}{'...' if len(interaction['response']) > 100 else ''}")
                print()
                continue
            elif user_input.lower() == 'stats':
                stats = agent.get_memory_stats()
                print(f"\n--- Memory Statistics ---")
                print(f"Total interactions: {stats['total_interactions']}")
                print(f"Factual queries: {stats['factual_count']}")
                print(f"Creative prompts: {stats['creative_count']}")
                print(f"Memory capacity: {stats['memory_capacity']}")
                print()
                continue
            elif user_input.lower() == 'clear':
                agent.clear_memory()
                print("Conversation memory cleared.\n")
                continue
            elif user_input.lower() == 'help':
                print("\nCommands:")
                print("  'exit' - Quit the program")
                print("  'memory' - Show conversation history")
                print("  'stats' - Show memory statistics")
                print("  'clear' - Clear conversation memory")
                print("  'help' - Show this help message\n")
                continue
            elif not user_input:
                continue
            
            # Process the input
            result = agent.process_input(user_input)
            print(f"Agent [{result['intent']}]: {result['response']}\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    # Verify OpenAI API key
    load_dotenv()
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment variables.")
        print("Please add your OpenAI API key to a .env file:")
        print("OPENAI_API_KEY=your_api_key_here")
        exit(1)
    
    print("🤖 AGENTIC LLM SYSTEM")
    print("Choose a mode:")
    print("1. Run comprehensive automated tests")
    print("2. Interactive mode (chat with the agent)")
    print("3. Quick demo")
    
    choice = input("\nEnter your choice (1, 2, or 3): ").strip()
    
    if choice == '1':
        run_comprehensive_tests()
    elif choice == '2':
        interactive_mode()
    elif choice == '3':
        # Quick demo
        print("\n=== QUICK DEMO ===")
        agent = AgenticLLM()
        
        demo_inputs = [
            "Who is the CEO of Google?",
            "Give me a caption for a futuristic city",
            "What's the largest planet in our solar system?",
            "Write a short poem about coding"
        ]
        
        for inp in demo_inputs:
            print(f"\nUser: {inp}")
            result = agent.process_input(inp)
            print(f"Agent [{result['intent']}]: {result['response']}")
    else:
        print("Invalid choice. Running comprehensive tests by default.")
        run_comprehensive_tests()