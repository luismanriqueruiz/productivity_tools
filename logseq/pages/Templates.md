- dailynotes
  template:: dailynotes
  template-including-parent:: false
	- # To do today
		- ## Existing tasks
			- {{query (task doing) }}
		- ## To do tasks
			- {{query (task TODO) }}

	- # Meetings
	- # What I did

- monthlynotes
  template:: monthlynotes
  template-including-parent:: false
	- # To do today
		- ## Existing tasks
			- {{query (task doing) }}
		- ## To do tasks
			- {{query (task TODO) }}
			- [TASK 1](https://www.example.com/task1) (not needed) #tool
				- Run: `example_queries.py`
			- Cost allocation
			- [TASK 2](https://www.example.com/task2) #tool
	- # Meetings
	- # What I did