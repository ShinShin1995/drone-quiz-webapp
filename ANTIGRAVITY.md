# AntiGravity Project Rules & Context

## Technical Stack
- **Architecture**: Single-page Web Application (pure frontend `.html` file).
- **Core Technology**: HTML5, Vanilla CSS3 (custom CSS design system with HSL variables, glassmorphism, responsive grid), and Vanilla JavaScript (ES6+).
- **Database**: Embedded static database of 588 exam questions inside the HTML file (`const database = [...]`).
- **State Persistence**: `localStorage` used for tracking practiced IDs, wrong question IDs, and question mastery level.

## Core Features
1. **Flexible Question Selection**: Selection of 20, 40, 50, 100, or All (remaining) questions. Filter by chapter.
2. **Full Coverage Selection**: Automatically prioritizes unpracticed questions. Triggers auto-reset once 100% of selected module is completed.
3. **Wrong Question Review Mode**: Isolates questions in `wrongIds` and automatically removes them upon a correct answer.
4. **Mastery Tracking**: Keeps track of consecutive correct answers. Marking a question as "fully mastered" when answered correctly 3 times in a row. Resets to 0 if wrong.
5. **Interactive Dashboard**: Top status bar displaying real-time metrics.

## Development Workflow
- Keep all HTML, CSS, and JS in a single `index.html` file to allow double-click execution directly in any browser without local server requirements.
