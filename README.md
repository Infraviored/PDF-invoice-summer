# Automated Invoice Summarizer

## Overview

This command-line tool automates the process of summarizing financial amounts from a directory of PDF invoices. It is designed to be robust and accurate, handling complexities such as various currency formats, invoice discounts, and duplicate files. When faced with ambiguity, it launches an interactive mode to ensure the final totals are correct, giving the user full control.

## Features

-   **Automated PDF Processing**: Converts all PDFs in a target directory to text for analysis.
-   **Duplicate Invoice Detection**: Before summarizing, the script identifies files with identical content, allows you to review them, and provides an option to delete redundant copies to ensure data integrity.
-   **Intelligent Amount Extraction**: Uses a precise regular expression to find monetary values, minimizing false positives by requiring an explicit currency symbol (`€` or `EUR`) next to the number.
-   **Sophisticated Discount Handling**: Automatically detects negative values (discounts) and attempts to apply them logically.
-   **Interactive Resolution Mode**: If a discount cannot be applied automatically, the script opens the relevant PDF and prompts the user for a decision, ensuring accuracy.
-   **User-Friendly CLI**: A simple command-line interface that can be aliased for easy access from anywhere in the terminal.

## Prerequisites

To function correctly, the script requires the `poppler-utils` package, which provides the essential `pdftotext` command for converting PDFs.

You can install it on Debian/Ubuntu-based systems with:
`bash
sudo apt-get install -y poppler-utils
`

## Setup and Usage

1.  **Save the Script**: Save the code as `summarize_invoices.py` in a memorable location (e.g., `/home/user/Programs/`).

2.  **Make it Executable**: Open a terminal and run the following command to grant execute permissions:
    `bash
    chmod +x /path/to/summarize_invoices.py
    `

3.  **Run the Script**: Execute the script by pointing it to a directory containing your PDF invoices.
    `bash
    /path/to/summarize_invoices.py /path/to/your/invoices/
    `

4.  **(Optional) Create a Bash Alias**: For easy access, you can add an alias to your `~/.bashrc` file.
    `bash
    echo "alias summarize_invoices='/path/to/summarize_invoices.py'" >> ~/.bashrc
    source ~/.bashrc
    `
    You can now run the script from any directory using `summarize_invoices .`.

---

## The Core Logic Explained

The script's primary goal is to extract the single, correct final amount from each invoice. It does this through a multi-stage process designed to handle complexity and ambiguity gracefully.

### Step 1: PDF Conversion & Duplicate Detection

When you run the script on a directory, it first creates a temporary, hidden directory to work in.

1.  **Conversion**: It iterates through every `.pdf` file in your target directory and uses the `pdftotext` command to convert each one into a plain `.txt` file inside the temporary directory.
2.  **Hashing**: Once all files are converted, the script reads the content of each text file and calculates a **SHA256 hash** for it. This hash serves as a unique fingerprint for the file's content.
3.  **Duplicate Identification**: The script checks if any two or more files share the same hash. If they do, they are marked as duplicates.
4.  **Interactive Duplicate Handling**: If duplicates are found, the script pauses its main analysis. It notifies you of the identical files, opens them for your review, and gives you an interactive prompt to delete one of the redundant PDF files. This ensures your source directory is clean before any financial analysis occurs.

### Step 2: Intelligent Amount Extraction

After ensuring the data is clean, the script analyzes the text of each invoice to find all potential monetary values.

1.  **Precise Regular Expression**: The core of the extraction is a regular expression designed for accuracy. It specifically looks for numerical values that are **immediately preceded or followed by a currency indicator** (`€` or `EUR`, case-insensitive). This strict requirement is crucial for avoiding the accidental extraction of non-monetary numbers like dates, order numbers, or street addresses.
2.  **Separating Amounts**: The regex also identifies if a number is preceded by a minus sign (`-`). The script builds two lists for each invoice:
    *   `positive_amounts`: A list of all standard costs and totals.
    *   `discounts`: A list of all negative values, treated as discounts.

### Step 3: Automatic Discount Application

If an invoice contains both positive amounts and discounts, the script attempts to resolve the final total automatically.

1.  **Identify Key Values**: It takes the single largest value from the `positive_amounts` list (assumed to be the subtotal or gross total) and the single largest value from the `discounts` list.
2.  **Calculate and Verify**: It calculates a potential final total by subtracting the largest discount from the largest positive amount (`potential_total = largest_positive - largest_discount`).
3.  **The Matching Rule**: The script then checks if this `potential_total` exists as another entry in the original `positive_amounts` list. If an exact match is found, it is highly probable that this is the correct, final paid amount. The script uses this calculated value and makes a note in the final report that the discount was successfully applied.

### Step 4: Interactive Resolution for Ambiguity

If the automatic logic in Step 3 fails, the script assumes the situation is ambiguous and requires human intelligence to resolve. This happens when subtracting the largest discount from the largest positive amount *does not* match any other positive number found in the invoice.

1.  **Trigger Interactive Mode**: The script flags the invoice and enters the interactive workflow.
2.  **Present Information**: It opens the PDF for you to review and prints the highest amount it found directly in the terminal for context.
3.  **User-Driven Choice**: It presents a clear menu:
    *   **[E]nter Manually**: Allows you to type the final, correct amount directly.
    *   **[S]kip**: Ignores all discounts and uses the highest positive amount found.
    *   **[1], [2], ...**: Allows you to select one or more of the detected discounts to apply.
4.  **Confirmation**: Once you make a selection, the script confirms the new final total and uses that user-verified amount in the final summary, adding a note that it was resolved manually. 