# TC: 01-core
### TC-F001-1: add 성공
- criterion: 1
- type: unit
- precondition: 빈 저장소
- steps: todo add x
- expected: 종료코드 0
- command: `python3 -m unittest tests.test_add`
### TC-F002-1: list 출력
- criterion: 1
- type: e2e
- precondition: x 가 추가됨
- steps: todo list
- expected: 출력에 x 포함
- command: `bash e2e.sh`
