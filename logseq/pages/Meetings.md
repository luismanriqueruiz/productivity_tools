# One day
	- {{query (and (property :title) (property :members) (property :document)(page "2025-12-22"))}}
	  query-sort-by:: page
	  query-table:: true
	  query-sort-desc:: true
	  query-properties:: [:page :title :members :document]
- # All days
	- {{query (and (property :title) (property :members) (property :document))}}
	  query-table:: true
	  query-properties:: [:page :title :members :document]
	  query-sort-by:: page
	  query-sort-desc:: true