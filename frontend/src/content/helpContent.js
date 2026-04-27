/**
 * Help / Support content: guides and troubleshooting.
 * Written for users with little technical knowledge. Plain language, step-by-step.
 * Guides may have: body (intro paragraph), sections (array of { label?, items } for bullet lists).
 */

export const guides = [
  {
    id: 'what-is-this-app',
    title: 'What is Research Workflow?',
    body: 'Research Workflow is a web app that moves your survey data from Qualtrics into other tools. For each study it runs a "pipeline":',
    sections: [
      {
        items: [
          'Fetches new survey responses from Qualtrics',
          'Processes them (including optional fraud checks)',
          'Sends data to Grid',
          'Stores files in Box',
        ],
      },
      {
        label: 'What you do:',
        items: [
          'Sign in with Google',
          'Pick a study',
          'Set up connections (Qualtrics, Grid, Box) in Connections & settings',
          'Click Start to run the pipeline',
        ],
      },
      {
        label: 'The app shows:',
        items: [
          'Progress through each stage',
          'Any errors so you can fix issues and run again',
        ],
      },
    ],
  },
  {
    id: 'getting-started',
    title: 'Getting started (first time)',
    sections: [
      {
        label: '1. Sign in',
        items: [
          'Open the app in your browser.',
          'If you are not signed in, you will see a sign-in page.',
          'Click "Sign in with Google" and choose your Google account.',
        ],
      },
      {
        label: '2. Find your study',
        items: [
          'After signing in, you are taken to the Studies list.',
          'If someone has already added you to a study, click the study name to open its Pipelines page.',
          'If you see "You don\'t have access to any studies yet," ask your team admin to add you to a study.',
        ],
      },
      {
        label: '3. Set up and run',
        items: [
          'Open a study and expand the "Connections & settings" section on the Pipelines page.',
          'Enter your Qualtrics, Grid, and Box credentials and IDs (see the guides below).',
          'Click "Save config," then click Start to run your first pipeline.',
        ],
      },
    ],
  },
  {
    id: 'studies-vs-pipelines',
    title: 'Studies and pipelines (what to click where)',
    body: 'A "study" is a project with its own settings and runs.',
    sections: [
      {
        label: 'Studies list:',
        items: [
          'Open Studies in the sidebar (or go to the dashboard) to see all studies you can access.',
          'Each study appears as a row; click it to open that study\'s Pipelines page.',
        ],
      },
      {
        label: 'Pipelines page (for one study):',
        items: [
          'Configure connections (Qualtrics, Grid, Box)',
          'Run the pipeline and see status',
          'View activity and errors',
        ],
      },
      {
        label: 'To switch studies:',
        items: [
          'Use the study name in the top bar (if you have more than one), or',
          'Go back to the Studies list and click another study.',
        ],
      },
    ],
  },
  {
    id: 'top-menu-and-profile',
    title: 'The top bar and profile menu',
    sections: [
      {
        label: 'On the top bar you see:',
        items: [
          'App name "Research Workflow"',
          'Current study name (when you are on a study\'s Pipelines page)',
          '"Pipelines" link to that study\'s main page',
          'Status badge: Idle, Running, Completed, Failed, or Stopped',
          'Start and Stop buttons (if you have permission)',
          'Your profile picture or initial',
        ],
      },
      {
        label: 'Click your profile picture to open the menu. From there you can go to:',
        items: [
          'Pipelines — the studies list',
          'Profile settings — your name and email',
          'Help & support — this page',
          'Admin — for each study you manage (only if you are an admin)',
          'Sign out',
        ],
      },
    ],
  },
  {
    id: 'connections-overview',
    title: 'Connections & settings: what it is',
    body: 'On the Pipelines page for a study, expand the section called "Connections & settings."',
    sections: [
      {
        label: 'Tabs inside:',
        items: [
          'Qualtrics — API token, survey ID, and data center',
          'Grid — API token and Grid study ID',
          'Box — Box folder and config',
          'Processing — skip already-processed responses',
          'Schedule — automatic runs',
          'Fraud detection — optional checks',
        ],
      },
      {
        label: 'Important:',
        items: [
          'You must fill in the right values before the pipeline can run.',
          'At the bottom, click "Save config" to apply your changes.',
          'Check "Save to file" if you want the app to remember settings after the server restarts (your admin can tell you if that is needed).',
          'Not sure where to get tokens or IDs? Ask your admin or the person who set up the study.',
        ],
      },
    ],
  },
  {
    id: 'qualtrics-tab',
    title: 'Qualtrics tab',
    sections: [
      {
        label: 'What you need:',
        items: [
          'Qualtrics API token — lets the app access your Qualtrics account',
          'Survey ID — which survey to export from',
          'Data Center — e.g. your Qualtrics data center hostname',
        ],
      },
      {
        label: 'Where to find them:',
        items: [
          'In your Qualtrics project under Survey settings, and in the URL or Qualtrics help docs.',
        ],
      },
      {
        label: 'Tips:',
        items: [
          'Tokens are like passwords — do not share them. The app hides them after you save; use "Show" only when you need to check or change.',
          'Leave a field empty to keep the existing saved value. Get the token from your Qualtrics account; ask your study manager if you do not have it.',
          'Enter the exact values; if they are wrong, the pipeline will fail when it tries to export from Qualtrics.',
        ],
      },
    ],
  },
  {
    id: 'grid-tab',
    title: 'Grid tab',
    sections: [
      {
        label: 'What you need:',
        items: [
          'Grid API token — lets the app access Grid and list studies.',
          'Grid study ID — the pipeline sends data to this "Grid study." Type the ID manually or click "Browse" to pick from a list.',
        ],
      },
      {
        label: 'Tips:',
        items: [
          'The app uses this study for subjects and events. Choose the correct study so data goes to the right place.',
          'Token is like a password — do not share it. Use "Show" only when you need to check or change it.',
        ],
      },
    ],
  },
  {
    id: 'box-tab',
    title: 'Box tab',
    sections: [
      {
        label: 'Step 1 — Box access:',
        items: [
          'If your study uses a Box "JWT config," you will see an area to upload a JSON file or paste the config.',
          'Do that first and save.',
        ],
      },
      {
        label: 'Step 2 — Box folder:',
        items: [
          'Set "Box folder to save video folders to": type the folder ID or click "Browse Box folders" to pick the folder.',
          'All pipeline output for this study will go under that folder.',
          'Make sure you have permission to write to that folder in Box.',
        ],
      },
    ],
  },
  {
    id: 'processing-schedule-fraud',
    title: 'Processing, Schedule, and Fraud detection tabs',
    sections: [
      {
        label: 'Processing:',
        items: [
          'Turn on "Skip already-processed responses" so the pipeline does not send the same survey response twice.',
          'This is usually left on.',
        ],
      },
      {
        label: 'Schedule:',
        items: [
          'Turn on "Enable scheduled runs" and set a schedule (e.g. daily at 9 AM) so the pipeline runs automatically.',
          'If a run is already in progress at that time, the scheduled run is skipped.',
        ],
      },
      {
        label: 'Fraud detection:',
        items: [
          'Enable checks that flag suspicious responses (e.g. very fast completion, duplicate IP addresses, straightlining).',
          'Your admin can explain which options to use for your study.',
        ],
      },
    ],
  },
  {
    id: 'running-the-pipeline',
    title: 'Running the pipeline',
    sections: [
      {
        label: 'To start a run:',
        items: [
          'Make sure Connections & settings are filled in and saved.',
          'Go to the top of the Pipelines page and click the green "Start" button.',
        ],
      },
      {
        label: 'What you will see:',
        items: [
          'Status badge changes to "Running."',
          'Pipeline stages (Qualtrics → Process → Grid → Box) update as each step runs.',
          'Progress bar and message below it show the current step.',
        ],
      },
      {
        label: 'When it finishes:',
        items: [
          'Status shows "Completed" (success) or "Failed" / "Stopped" (something went wrong).',
          'You can click "Stop" anytime to cancel a run in progress.',
          'Only one run can be in progress at a time for that study.',
        ],
      },
    ],
  },
  {
    id: 'pipeline-status-and-stages',
    title: 'Understanding pipeline status and stages',
    sections: [
      {
        label: 'Status badge (top of page):',
        items: [
          'Idle — nothing running',
          'Running — pipeline is running',
          'Completed — finished successfully',
          'Failed — finished with an error',
          'Stopped — you or the system stopped it',
        ],
      },
      {
        label: 'Pipeline section (four stages):',
        items: [
          'Qualtrics → Process → Grid → Box',
          'As the run progresses, each stage turns from gray to active to green when done.',
          'If something fails, the stage where it failed is highlighted in red — use this to see how far the run got.',
        ],
      },
      {
        label: 'Progress bar:',
        items: [
          'The bar and text under it describe the current step in plain language (e.g. "Qualtrics export" or "Box upload").',
        ],
      },
    ],
  },
  {
    id: 'activity-and-errors',
    title: 'Activity and errors',
    sections: [
      {
        label: 'Activity & errors (lower on the Pipelines page):',
        items: [
          'Activity list — recent events for this study (e.g. exports, uploads).',
          'Error log — error messages from the last run.',
        ],
      },
      {
        label: 'When a run fails:',
        items: [
          'Look at the Error log first — it usually says what went wrong (e.g. invalid token, missing survey ID).',
          'Fix the issue in Connections & settings and try again.',
          'If you do not understand the error, copy it and ask your admin or support.',
        ],
      },
    ],
  },
  {
    id: 'profile-and-account',
    title: 'Profile settings and your account',
    sections: [
      {
        items: [
          'Click your profile picture (top right) and choose "Profile settings."',
          'You will see your name and email as reported by Google.',
          'Your account is managed by Google sign-in; the app does not store a separate password.',
          'To sign out, use "Sign out" in the same profile menu.',
        ],
      },
    ],
  },
  {
    id: 'for-study-admins',
    title: 'For study admins: creating studies and managing users',
    sections: [
      {
        label: 'Where to find admin:',
        items: [
          'If you are an admin, you will see "Admin" in the profile menu (and possibly "Create study" on the Studies list).',
          'Click "Admin" for a study to open the study admin page.',
        ],
      },
      {
        label: 'On the study admin page you can:',
        items: [
          'Edit the study name and description',
          'Add or remove users and set their role (viewer, editor, or admin)',
          'Delete the study (use with care)',
        ],
      },
      {
        label: 'Roles:',
        items: [
          'Viewer — can only view',
          'Editor — can change settings and run the pipeline',
          'Admin — can do everything, including managing users',
        ],
      },
      {
        label: 'To create a new study:',
        items: [
          'Go to the Studies list and click "Create study."',
          'Enter a name and optional description, then create.',
          'You will be taken to that study\'s Admin page to add users and set up connections.',
        ],
      },
    ],
  },
]

/**
 * Troubleshooting entries. Use steps (array) for numbered "what to try" lists,
 * or solution (string) for a single note. Optional bullets for checklists.
 * problem can be a string or an array of strings (rendered as bullets).
 */
export const troubleshooting = [
  {
    id: 'cannot-sign-in',
    title: 'I cannot sign in or the page says I am not logged in',
    problem: 'The app could not sign you in with Google, or your session expired.',
    steps: [
      'Make sure you are using a supported browser (e.g. Chrome, Firefox, Edge) and that cookies are allowed.',
      'Click "Sign in with Google" again and complete the Google sign-in flow. If Google blocks the sign-in, check that your organization allows this app.',
      'If you are sent back to the login page right after signing in, the server may be down or misconfigured. Ask your admin to check that the app server is running and that the login redirect URL is set correctly.',
    ],
  },
  {
    id: 'no-studies-show',
    title: 'I do not see any studies',
    problem: 'The Studies list is empty or says you do not have access to any studies.',
    steps: [
      'You must be added to a study by someone who already has admin access. Contact your team or project admin and ask them to add your email to the study (they do this in Admin → Study users).',
      'If you are an admin elsewhere, you can create a new study from the Studies list by clicking "Create study" and then adding yourself and others in the Admin page.',
    ],
  },
  {
    id: 'backend-not-found',
    title: '"Backend not found" or "Backend took too long" or the page will not load',
    problem: 'The app in your browser cannot reach the server that runs the pipeline.',
    steps: [
      'The server that hosts the app may be stopped or unreachable. Ask your admin to start it or check the server status.',
      'If you run the app yourself, start it from the project folder using the instructions your team provided. Do not start it from a different directory.',
      'Check your internet connection and that you are using the correct web address (URL) for the app.',
    ],
  },
  {
    id: 'pipeline-fails',
    title: 'The pipeline fails or I see errors in the activity list',
    problem: [
      'A run did not complete successfully, or you see error messages.',
      'Common causes: wrong or expired tokens, wrong Survey ID or Data Center, wrong Grid study ID or Box folder ID.',
    ],
    steps: [
      'Scroll down to "Activity & errors" and open the Error log. Read the error message — it often says what went wrong (e.g. "Invalid API token," "Survey not found").',
      'Go to Connections & settings and check that every required field is filled in and correct.',
      'If the error mentions a specific service (Qualtrics, Grid, or Box), double-check that tab. Make sure the token has the right permissions and the IDs exist and you have access to them.',
    ],
    bullets: [
      'Qualtrics API token, Survey ID, and Data Center',
      'Grid API token and Grid study ID',
      'Box config (if used) and Box folder ID',
    ],
  },
  {
    id: 'box-404',
    title: '"Box folders API not found (404)" or Box folder list will not load',
    problem: 'The app cannot load your Box folders, so you cannot use "Browse Box folders."',
    steps: [
      'Make sure Box is set up correctly for this study. In the Box tab, if there is a "Box config" section, upload or paste the Box JWT config JSON and save it.',
      'Ask your admin to restart the server from the project folder (not from a different directory). Sometimes the Box config path or environment needs to be set when the server starts.',
      'If the problem continues, your admin may need to check the server logs or Box configuration.',
    ],
  },
  {
    id: 'start-button-disabled',
    title: 'The Start button is grayed out or I do not see Start/Stop',
    problem: 'You cannot start or stop the pipeline.',
    steps: [
      'Only users with "editor" or "admin" role can run the pipeline. If you have "viewer" role, ask a study admin to change your role to editor or admin.',
      'You cannot start a new run while one is already in progress. Wait for the current run to finish (or ask an editor/admin to stop it), then try again.',
    ],
  },
  {
    id: 'scheduled-skipped',
    title: 'A scheduled run did not start',
    problem: 'You have scheduling turned on but the pipeline did not run at the scheduled time.',
    solution: 'If a run was already in progress at that time, the app skips the scheduled run on purpose so two runs do not run at once. The next scheduled time will run as planned. If no run was in progress and it still did not run, ask your admin to check that the server is running and that the schedule (cron and time zone) is set correctly.',
  },
  {
    id: 'save-config-not-sticking',
    title: 'My settings do not save or disappear after I leave the page',
    problem: 'After clicking "Save config," the values seem to reset or are not used on the next run.',
    steps: [
      'Make sure you clicked "Save config" after changing any values. Changes are not applied until you save.',
      'If the server restarts (e.g. after a deploy), settings are lost unless "Save to file" was checked when you saved. Ask your admin whether your setup uses file persistence; if yes, check "Save to file" when saving.',
      'If you have multiple studies, confirm you are editing the correct study. Each study has its own settings.',
    ],
  },
  {
    id: 'grid-browse-empty',
    title: 'When I click "Browse" for Grid, no studies appear',
    problem: 'The Grid study picker is empty or says there are no studies.',
    steps: [
      'Your Grid API token must have permission to list studies. Check that the token in the Grid tab is correct and has the right scope.',
      'You may not have access to any Grid studies with that token. Log into Grid separately and confirm you can see studies there; use the same account or token the app is using.',
      'If the app shows an error in the modal, read it and fix the issue (e.g. invalid token) in the Grid tab.',
    ],
  },
]
