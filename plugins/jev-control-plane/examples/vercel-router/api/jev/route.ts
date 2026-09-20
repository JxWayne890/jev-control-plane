import { timingSafeEqual } from 'node:crypto';
import { experimental_evaluate as evaluate } from 'ai';

export const runtime = 'nodejs';

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

type RouterRequest = {
  prompt?: unknown;
  context?: JsonValue;
};

function authorized(request: Request): boolean {
  const expected = process.env.JEV_ROUTER_SHARED_SECRET;
  const supplied = request.headers.get('authorization')?.replace(/^Bearer\s+/i, '');

  if (!expected || !supplied) return false;

  const expectedBytes = Buffer.from(expected);
  const suppliedBytes = Buffer.from(supplied);
  return (
    expectedBytes.length === suppliedBytes.length &&
    timingSafeEqual(expectedBytes, suppliedBytes)
  );
}

export async function POST(request: Request) {
  if (!authorized(request)) {
    return Response.json({ error: 'unauthorized' }, { status: 401 });
  }

  let body: RouterRequest;
  try {
    body = (await request.json()) as RouterRequest;
  } catch {
    return Response.json({ error: 'invalid_json' }, { status: 400 });
  }

  if (typeof body.prompt !== 'string' || body.prompt.length > 12_000) {
    return Response.json({ error: 'invalid_prompt' }, { status: 400 });
  }

  const result = await evaluate({
    model: 'typesafe-ai/jev',
    state: {
      prompt: body.prompt,
      context: body.context,
    },
    questions: {
      scopeStatus: {
        type: 'choice',
        instructions: 'How does this request relate to the registered project scope?',
        criteria: {
          inside_scope: 'Directly included in required scope.',
          necessary_dependency: 'Not named, but necessary to complete approved scope.',
          change_request: 'Conflicts with or adds to an explicit scope boundary.',
          unrelated: 'Belongs to a different project or outcome.',
          unknown: 'The available context cannot establish scope.',
        },
      },
      riskLevel: {
        type: 'choice',
        instructions: 'What is the operational risk of performing this request?',
        criteria: {
          low: 'Read only or easily reversible local work.',
          medium: 'Integration, schema, deployment preparation, or meaningful code change.',
          high: 'Production, authentication, permissions, billing, secrets, or costly reversal.',
          critical: 'Destructive or potentially irreversible action.',
        },
      },
      reversibility: {
        type: 'choice',
        instructions: 'How difficult would it be to reverse the requested work?',
        criteria: {
          easy: 'Straightforward rollback with little or no persistent impact.',
          costly: 'Rollback requires coordination, migration, or service recovery.',
          difficult: 'Rollback may lose data, disrupt production, or be incomplete.',
        },
      },
      threadAction: {
        type: 'choice',
        instructions: 'Should Codex keep this work in the current thread or create a new thread?',
        criteria: {
          reuse_current: 'A continuation or a small task that benefits from current context.',
          create_new: 'A distinct deliverable, isolated risk, or substantial new workstream.',
        },
      },
      worktreeRecommended: {
        type: 'choice',
        instructions: 'Should a new delegated task use an isolated Git worktree?',
        criteria: {
          yes: 'The work changes repository files and benefits from isolation.',
          no: 'The work is read only, projectless, or does not need isolation.',
        },
      },
      modelProfile: {
        type: 'choice',
        instructions: 'Which execution profile best fits this request?',
        criteria: {
          rapid_decision: 'Short classification, retrieval, or simple explanation.',
          balanced_build: 'Ordinary implementation with moderate reasoning.',
          complex_build: 'Architecture, difficult debugging, or broad technical synthesis.',
          critical_review: 'High risk, production, security, billing, or destructive work.',
        },
      },
      reasoningEffort: {
        type: 'choice',
        instructions: 'How much reasoning should the execution model use?',
        criteria: {
          low: 'A direct answer or bounded classification.',
          medium: 'Normal implementation and verification.',
          high: 'Complex, ambiguous, or high risk work.',
        },
      },
    },
    providerOptions: {
      gateway: { zeroDataRetention: true },
    },
  });

  const confidence = result.providerMetadata?.typesafe?.confidence as
    | Record<string, number>
    | undefined;
  const answers = result.answers;

  return Response.json({
    provider: 'jev',
    model: 'typesafe-ai/jev',
    decision: {
      scopeStatus: answers.scopeStatus.choice,
      riskLevel: answers.riskLevel.choice,
      reversibility: answers.reversibility.choice,
      threadAction: answers.threadAction.choice,
      worktreeRecommended: answers.worktreeRecommended.choice === 'yes',
      modelProfile: answers.modelProfile.choice,
      reasoningEffort: answers.reasoningEffort.choice,
    },
    confidence: confidence ?? {},
  });
}
