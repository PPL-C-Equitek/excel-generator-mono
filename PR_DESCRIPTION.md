## Summary

This PR implements the strategy pattern for file validation to improve code maintainability and extensibility in the file processing pipeline.

Main changes:
- Implement strategy pattern for file validation in `backend/file_processing/services/file_validation_strategy.py`
- Add comprehensive tests for the new validation strategy pattern
- Refactor file validation logic to use strategies for different file types
- Improve separation of concerns in file processing services

## How to Test

1. Check out this branch and install dependencies.
   - Backend: run tests with `python manage.py test` or `pytest`
   - Frontend: run tests with `npm test`
2. Run specific tests for file validation strategy.
3. Verify the following functionality:
   - File validation strategy correctly handles different file types
   - Strategy pattern allows easy addition of new validation types
   - All existing file processing tests pass without regression

Specific testing steps:
- Run backend tests: `cd backend && python manage.py test file_processing.tests.test_file_validation_strategy`
- Run frontend tests: `npm test -- tests/`
- Verify file upload and processing workflow still works end-to-end

## Related Issues

- None referenced in commit messages.

## Author Checklist

- [ ] Code follows team coding standards and style guide
- [ ] Self-reviewed the code changes
- [ ] Added/updated tests for new functionality
- [ ] All tests pass locally
- [ ] Code is properly documented
- [ ] Synced with latest `main` branch
- [ ] PR title follows conventional commit format
- [ ] Meaningful commit messages used

## Additional Notes

- Generated from commit history on `refactor/process-upload-strategy` branch.
- Focus: Code refactoring with strategy pattern implementation and comprehensive test coverage.
- 2 commits with changes to backend file processing and tests.

## Type of task

- [ ] Data Processing (for tasks involving data handling or manipulation)
- [ ] Model Training (for tasks involving model training)
- [ ] API Development (for developing or serving model via API)
- [ ] UI Development (for developing or improving user interface)
- [x] Testing (for writing or updating tests)
- [ ] Debugging (for fixing errors or investigating issues)
- [x] Refactor (for code improvements without changing functionality)
- [ ] Performance Improvement / Optimization (for optimizations related to speed or efficiency)
- [ ] Security (for tasks related to security updates or patches)
- [ ] Documentation (for updating or improving documentation)
- [ ] Monitoring (for adding or updating monitoring capabilities)
- [ ] All

## Reviewer(s)

- [ ] @username1
- [ ] @username2
- [ ] @username3

