---
id: spec-driven-development
name: Spec-Driven Development
description: Build features from specifications - write spec first, then implement
category: planning
trigger_phrases: ["spec", "specification", "requirements", "规格", "需求"]
priority: 10
---

# Spec-Driven Development

## Overview

Build features by writing specifications first, then implementing code that satisfies those specs. This ensures clear requirements, testable outcomes, and predictable delivery.

## When to Use

- Starting a new feature or module
- Requirements are complex or ambiguous
- Multiple stakeholders need alignment
- You want to reduce rework

## Workflow

### Phase 1: Requirements Analysis
1. Gather all stakeholder requirements
2. Identify edge cases and constraints
3. Document acceptance criteria
4. Validate with stakeholders

### Phase 2: Specification Writing
1. Write detailed specification document
2. Include API contracts, data models, user flows
3. Define success metrics
4. Get spec reviewed by team

### Phase 3: Technical Design
1. Design architecture to meet spec
2. Identify dependencies and risks
3. Create implementation plan
4. Estimate timeline

### Phase 4: Implementation
1. Implement feature according to spec
2. Write tests alongside code
3. Continuously validate against spec
4. Update spec if requirements change

### Phase 5: Testing & Validation
1. Run all acceptance tests
2. Validate against original spec
3. Get stakeholder sign-off
4. Document any deviations

### Phase 6: Shipping
1. Deploy to production
2. Monitor against success metrics
3. Gather feedback
4. Iterate based on learnings

## Best Practices

- ✅ Specs should be living documents
- ✅ Involve all stakeholders early
- ✅ Define measurable acceptance criteria
- ✅ Update specs when requirements change
- ❌ Don't skip spec for "simple" features
- ❌ Don't implement without validated spec

## References

- Source: https://github.com/addyosmani/agent-skills
- Related: test-driven-development, code-review
