#!/usr/bin/env python3
import os
import re
import argparse
import subprocess
import sys
import tempfile
import shutil
from collections import namedtuple
import hashlib

# Updated data structure to hold a more detailed analysis
InvoiceData = namedtuple('InvoiceData', ['total', 'notes', 'status', 'positive_amounts', 'discounts'])

STATUS_OK = 'OK'
STATUS_APPLIED_DISCOUNT = 'APPLIED_DISCOUNT'
STATUS_NEEDS_INTERACTION = 'NEEDS_INTERACTION'
STATUS_NO_AMOUNT = 'NO_AMOUNT'

def detect_and_handle_duplicates(text_dir, pdf_dir):
    """Detects duplicate invoices based on text content and handles them interactively."""
    hashes = {}
    for filename in os.listdir(text_dir):
        if filename.endswith('.txt'):
            file_path = os.path.join(text_dir, filename)
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
                if file_hash not in hashes:
                    hashes[file_hash] = []
                hashes[file_hash].append(filename)
    
    duplicates_found = False
    for file_hash, filenames in hashes.items():
        if len(filenames) > 1:
            duplicates_found = True
            print("\n" + "="*80)
            print("--- DUPLICATE INVOICES DETECTED ---")
            print("The following files have identical content:")
            for f in filenames:
                print(f"  - {f}")
            
            print("Opening the corresponding PDFs for review...")
            for f in filenames:
                pdf_path = os.path.join(pdf_dir, os.path.splitext(f)[0] + '.pdf')
                if os.path.exists(pdf_path):
                    try:
                        if sys.platform == "win32": os.startfile(pdf_path)
                        else: subprocess.Popen(['xdg-open' if sys.platform.startswith('linux') else 'open', pdf_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"Error opening PDF {pdf_path}: {e}", file=sys.stderr)

            while True:
                choice = input("Do you want to delete one of these files? [y/n]: ").lower()
                if choice in ['y', 'yes']:
                    print("\nWhich file do you want to delete?")
                    for i, f in enumerate(filenames):
                        print(f"  [{i+1}] {f}")
                    print(f"  [{len(filenames)+1}] Cancel")
                    
                    try:
                        del_choice = int(input("Your choice: "))
                        if 1 <= del_choice <= len(filenames):
                            file_to_delete_txt = filenames[del_choice-1]
                            file_to_delete_pdf = os.path.join(pdf_dir, os.path.splitext(file_to_delete_txt)[0] + '.pdf')
                            if os.path.exists(file_to_delete_pdf):
                                os.remove(file_to_delete_pdf)
                                print(f"Deleted: {file_to_delete_pdf}")
                            else:
                                print(f"Error: File not found at {file_to_delete_pdf}")
                            break
                        elif del_choice == len(filenames)+1:
                            print("Deletion cancelled.")
                            break
                        else:
                            print("Invalid choice.")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
                elif choice in ['n', 'no']:
                    break
    
    return duplicates_found

def check_pdftotext_installed():
    """Checks if pdftotext is in the system's PATH."""
    if not shutil.which("pdftotext"):
        print("Error: 'pdftotext' command not found.", file=sys.stderr)
        print("Please install poppler-utils (or equivalent for your OS).", file=sys.stderr)
        print("On Debian/Ubuntu: sudo apt-get install poppler-utils", file=sys.stderr)
        sys.exit(1)

def convert_pdfs_to_text(pdf_dir, text_dir):
    """Converts all PDFs in a directory to text files."""
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"No PDF files found in '{pdf_dir}'.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(pdf_files)} PDF files. Converting to text...")
    for filename in pdf_files:
        pdf_path = os.path.join(pdf_dir, filename)
        txt_filename = os.path.splitext(filename)[0] + '.txt'
        txt_path = os.path.join(text_dir, txt_filename)
        try:
            subprocess.run(['pdftotext', pdf_path, txt_path], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to convert {filename}: {e.stderr}", file=sys.stderr)
    print("Conversion complete.")

def analyze_invoice_text(content):
    """Extracts amounts and determines if discounts can be auto-applied or need interaction."""
    pattern = re.compile(
        r'(-\s*)?'
        r'(?:'
        r'(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))'
        r'|'
        r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))\s*(?:€|EUR)'
        r')', re.IGNORECASE)

    positive_amounts, discounts = [], []
    for match in pattern.finditer(content):
        sign, num_before, num_after = match.groups()
        num_str = num_before or num_after
        cleaned_num_str = num_str.replace('.', '').replace(',', '.')
        try:
            amount = float(cleaned_num_str)
            if sign:
                discounts.append(amount)
            else:
                positive_amounts.append(amount)
        except ValueError:
            continue

    if not positive_amounts:
        return InvoiceData(None, "No amount found", STATUS_NO_AMOUNT, [], [])

    positive_amounts.sort(reverse=True)
    discounts.sort(reverse=True)

    if not discounts:
        return InvoiceData(positive_amounts[0], "", STATUS_OK, positive_amounts, discounts)

    main_total = positive_amounts[0]
    calculated_total = round(main_total - discounts[0], 2)

    if calculated_total in [round(p, 2) for p in positive_amounts]:
        notes = f"Discounts found: {', '.join([f'-{d:.2f}' for d in discounts])}. Applied -{discounts[0]:.2f}."
        return InvoiceData(calculated_total, notes, STATUS_APPLIED_DISCOUNT, positive_amounts, discounts)
    else:
        notes = f"Discounts found: {', '.join([f'-{d:.2f}' for d in discounts])}. WARNING: Could not automatically apply."
        return InvoiceData(main_total, notes, STATUS_NEEDS_INTERACTION, positive_amounts, discounts)

def interactive_discount_resolver(filename, pdf_dir, positive_amounts, discounts):
    """Guides the user with a more intuitive, multi-select, streamlined flow."""
    print("\n" + "="*80)
    print(f"--- INTERACTIVE MODE: {filename} ---")
    print("This invoice has discounts that could not be applied automatically.")
    print("Opening the PDF for review...")

    pdf_path = os.path.join(pdf_dir, os.path.splitext(filename)[0] + '.pdf')
    if os.path.exists(pdf_path):
        try:
            # Always open the PDF in the background, redirecting output to suppress messages
            if sys.platform == "win32":
                os.startfile(pdf_path)
            else:
                viewer = 'xdg-open' if sys.platform.startswith('linux') else 'open'
                subprocess.Popen([viewer, pdf_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Error opening PDF: {e}", file=sys.stderr)
    else:
        print(f"Original PDF not found at {pdf_path}")

    print(f"\nThe highest amount found is: {positive_amounts[0]:.2f} €")
    print("\nHow would you like to resolve this?")
    print("  [E] Enter the final correct amount manually")
    print("  [S] Skip (use original highest value)")
    for i, d in enumerate(discounts):
        print(f"  [{i+1}] Apply discount of {d:.2f} €")
    
    print("\nEnter 'E', 'S', or discount numbers separated by commas (e.g., 1,2).")

    while True:
        try:
            choice_str = input("Your choice: ").strip().upper()
            
            if choice_str == 'E':
                while True:
                    try:
                        custom_total = float(input("Enter the final correct amount (e.g., 123.45): "))
                        final_total = custom_total
                        notes = "Manually entered total."
                        break
                    except ValueError:
                        print("Invalid amount. Please enter a number.")
                break
            elif choice_str == 'S':
                final_total = positive_amounts[0]
                notes = "Skipped discount in interactive mode."
                break
            
            # Handle multi-select for discounts
            choices = [int(c.strip()) for c in choice_str.split(',')]
            selected_discounts_values = []
            valid_choices = True
            
            for c in choices:
                if 1 <= c <= len(discounts):
                    selected_discounts_values.append(discounts[c-1])
                else:
                    print(f"Invalid selection: {c}. Choices must be between 1 and {len(discounts)}.")
                    valid_choices = False
                    break
            
            if not valid_choices:
                continue

            if selected_discounts_values:
                total_discount = sum(selected_discounts_values)
                final_total = round(positive_amounts[0] - total_discount, 2)
                applied_discounts_str = ', '.join([f"{d:.2f}" for d in selected_discounts_values])
                notes = f"Manually applied discount(s) of {applied_discounts_str}."
                break
            else:
                print("No valid discounts selected.")

        except ValueError:
            print("Invalid input. Please enter 'E', 'S', or numbers separated by commas.")

    print(f"The final amount for this invoice will be {final_total:.2f} €.")
    print("="*80)
    return final_total, notes

def main():
    parser = argparse.ArgumentParser(
        description="Converts PDF invoices, detects duplicates, and summarizes total amounts with interactive discount handling.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('directory', nargs='?', default='.',
                        help="Path to the directory containing PDF invoices.\nDefaults to the current directory.")
    args = parser.parse_args()

    invoice_dir = os.path.abspath(args.directory)
    if not os.path.isdir(invoice_dir):
        print(f"Error: Directory not found at '{invoice_dir}'", file=sys.stderr)
        sys.exit(1)

    check_pdftotext_installed()

    with tempfile.TemporaryDirectory() as temp_dir:
        convert_pdfs_to_text(invoice_dir, temp_dir)

        # Step 1: Detect and handle duplicates
        if detect_and_handle_duplicates(temp_dir, invoice_dir):
            print("\nDuplicates were found and handled. Please re-run the script for an accurate summary.")
            sys.exit(0)

        # Step 2: Proceed with analysis if no duplicates were found
        invoice_files = [f for f in os.listdir(temp_dir) if f.endswith('.txt')]
        print(f"\nProcessing {len(invoice_files)} invoices...")
        results = []

        # First pass: Analyze all files
        for filename in sorted(invoice_files):
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            invoice_data = analyze_invoice_text(content)
            results.append((filename, invoice_data))

        # Second pass: Handle interactions
        final_results = []
        for filename, invoice_data in results:
            if invoice_data.status == STATUS_NEEDS_INTERACTION:
                new_total, new_notes = interactive_discount_resolver(
                    filename, invoice_dir, invoice_data.positive_amounts, invoice_data.discounts
                )
                final_results.append({'file': filename, 'total': new_total, 'notes': new_notes})
            else:
                final_results.append({'file': filename, 'total': invoice_data.total, 'notes': invoice_data.notes})

        # Final output
        grand_total = 0
        invoice_count = len(final_results)
        print("\n" + "-" * 80)
        print(f"{'Invoice File':<25} {'Amount (€)':>12} {'Notes'}")
        print("-" * 80)

        for result in final_results:
            total = result.get('total')
            notes = result.get('notes', '')
            if total is not None:
                grand_total += total
                print(f"{result['file']:<25} {total:>12.2f} {notes}")
            else:
                print(f"{result['file']:<25} {'Not found':>12} {notes}")

        print("-" * 80)
        grand_total_str = f"Grand Total ({invoice_count} items)"
        print(f"{grand_total_str:<25} {grand_total:>12.2f}")
        print("-" * 80)

if __name__ == "__main__":
    main() 