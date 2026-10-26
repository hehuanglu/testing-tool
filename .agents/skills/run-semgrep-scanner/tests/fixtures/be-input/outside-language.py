# Synthetic Python surface outside the selected TypeScript rule's language.
# Zero native results for that rule cannot answer this source question.
def search(request, database):
    database.execute("SELECT * FROM records WHERE label = " + request["filter"])
