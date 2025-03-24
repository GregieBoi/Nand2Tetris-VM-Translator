import sys
import os
import argparse

SEGMENTS = {"local": "LCL", "argument": "ARG", "this": "THIS", "that": "THAT", "temp": "5", "static": "16", "pointer": "3"}

argparser = argparse.ArgumentParser(description="Translates the Nand2Tetris VM to assembly code")
argparser.add_argument("-i", "--input", type=str, help="Path to Input file", required=True)
argparser.add_argument("-o", "--output", help="Path to Output file", required=False, default="default.asm")

COUNTER = 0

class VMTranslator:
  def __init__(self):
    self.handleArguments()

    self.parser: Parser = Parser(argparser.parse_args().input)

    outputFile = argparser.parse_args().output
    if (outputFile == "default.asm"):
      outputFile = argparser.parse_args().input.split(".")[0] + ".asm"

    self.code: CodeWriter = CodeWriter(outputFile)

  def handleArguments(self):
    arguments = argparser.parse_args()

    if not os.path.exists(arguments.input):
      KeyError("Input file does not exist")
      argparser.print_help()
      exit(1)

    if arguments.output:
      if os.path.exists(arguments.output):
        KeyError("Output file already exists")
        argparser.print_help()
        exit(1)

  def translate(self):
    
    while self.parser.hasMoreLines():

      command = self.parser.commandType()
      if command == "C_PUSH" or command == "C_POP":
        arg1 = self.parser.arg1()
        arg2 = self.parser.arg2()
        self.code.writePushPop(command, arg1, arg2)
      elif command == "C_ARITHMETIC":
        arg1 = self.parser.arg1()
        self.code.writeArithmetic(arg1)

      self.parser.advance()

    self.code.halt()

    self.code.close()

# Handles the parsing of a single .vm file
class Parser:
  # Opens the input file/stream, and gets ready to parse it
  def __init__(self, inputFile: str):
    self.file = open(inputFile, "r")
    self.cleanUp()

  def cleanUp(self):
    with open("vm_code/intermediate.vm", "w") as f:
      for line in self.file.readlines():
        split = line.split("//")
        if len(split) > 1:
          line = split[0]
        if line.isspace() or line == "\n" or line == "":
          continue
        f.write(line)

    self.file = open("vm_code/intermediate.vm", "r")

  # Are there more lines in the input?
  def hasMoreLines(self) -> bool:
    pos = self.file.tell()
    nextLine = bool(self.file.readline())
    self.file.seek(pos)
    return nextLine

  # Reads the next command from the input and makes it the current command
  # This method should be called only if hasMoreLines() returns true
  # Initially there is no current command
  def advance(self):
    while self.hasMoreLines():
      line = self.file.readline()
      line = ''.join(line.split())
      if line.isspace():
        continue
      if "//" in line:
        beforeComment = line.split("//")[0]
        if beforeComment.isspace():
          continue
      return

  # Returns a constand representing the type of the current command
  # If the current command is an arithmetic-logical command, returns
  # C_ARITHMETIC
  def commandType(self) -> str:
    pos = self.file.tell()
    line = self.file.readline()
    if "push" in line:
      ret = "C_PUSH"
    elif "pop" in line or ";" in line:
      ret = "C_POP"
    else:
      ret = "C_ARITHMETIC"
    self.file.seek(pos)
    return ret

  # Returns the first argument of the current command
  # In the case of C_ARITHMETIC, the command itself (add, sub, etc.) is returned
  # --Should not be called if the current command is C_RETURN--
  def arg1(self) -> str:
    pos = self.file.tell()
    line = self.file.readline()
    split = line.split()
    self.file.seek(pos)
    return split[1] if len(split) > 1 else split[0]

  # Returns the second argument of the current command
  # Should be called only if the current command is C_PUSH, C_POP, --C_FUNCTION, or C_CALL--
  def arg2(self) -> str:
    pos = self.file.tell()
    line = self.file.readline()
    split = line.split()
    self.file.seek(pos)
    return split[2]


# Generates assembly code from the parsed VM command
class CodeWriter:
  # Opens an output file/stream and gets ready to write into it
  def __init__(self, outputFile: str):
    self.outputFile = open(outputFile, "w")

  # Writes to the output file the assembly code that implements the given arithmetic-logical command

  # add - pop the top two values from the stack, add them, and push the result
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=D+M   // add the second value to the working value                         A=X-2, M=MY, D=MX+MY
  # M=D     // store the result in the working address                           A=X-2, M=MX+MY, D=MY+MY

  # sub - pop the top two values from the stack, subtract the first from the second, and push the result
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=M-D   // add the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # M=D     // store the result in the working address                           A=X-2, M=MY-MX, D=MY-MX

  # neg - pop the top value from the stack, negate it, and push the result
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # D=M-1   // store the decremented stack pointer in the working value          A=0, M=X-1, D=X-1
  # A=D     // set the working address to the working value                      A=X-1, M=MX, D=X-1
  # M=-M    // negate the top value on the stack                                 A=X-1, M=-MX, D=X-1

  # eq - pop the top two values from the stack, if the first is equal to the second, push 1, otherwise push 0
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=M-D   // add the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # @EQ     // set working address to EQ                                         A=EQ, M=MEQ, D=MY-MX
  # D;JEQ   // if the result is zero, jump to EQ                                 A=EQ, M=MEQ, D=MY-MX
  # D=0     // set the working value to zero                                     A=EQ, M=MEQ, D=0
  # @PUSH   // set the working address to PUSH                                   A=PUSH, M=MPUSH, D=0
  # D;JMP   // jump to PUSH irregardless
  # (EQ)    // where EQ is
  # D=1     // set the working value to one                                      A=EQ, M=MEQ, D=1
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP                                     A=0, M=X-1, D=1|0
  # A=M-1     // set the working address to the stack pointer                    A=X-1, M=MX, D=1|0
  # M=D     // set the value at the working address to the working value         A=X-1, M=1|0, D=1|0

  # gt - pop the top two values from the stack, if the second is greater than the first, push 1, otherwise push 0
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=M-D   // sub the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # @GT     // set working address to EQ                                         A=EQ, M=MEQ, D=MY-MX
  # D;JGT   // if the result is zero, jump to EQ                                 A=EQ, M=MEQ, D=MY-MX
  # D=0     // set the working value to zero                                     A=EQ, M=MEQ, D=0
  # @PUSH   // set the working address to PUSH                                   A=PUSH, M=MPUSH, D=0
  # D;JMP   // jump to PUSH irregardless
  # (GT)    // where EQ is
  # D=1     // set the working value to one                                      A=EQ, M=MEQ, D=1
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP                                     A=0, M=X-1, D=1|0
  # A=M-1     // set the working address to the stack pointer                    A=X-1, M=MX, D=1|0
  # M=D     // set the value at the working address to the working value         A=X-1, M=1|0, D=1|0

  # lt - pop the top two values from the stack, if the second is less than the first, push 1, otherwise push 0
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=D-M   // sub the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # @LT     // set working address to EQ                                         A=EQ, M=MEQ, D=MY-MX
  # D;JLT   // if the result is zero, jump to EQ                                 A=EQ, M=MEQ, D=MY-MX
  # D=0     // set the working value to zero                                     A=EQ, M=MEQ, D=0
  # @PUSH   // set the working address to PUSH                                   A=PUSH, M=MPUSH, D=0
  # D;JMP   // jump to PUSH irregardless
  # (LT)    // where EQ is
  # D=1     // set the working value to one                                      A=EQ, M=MEQ, D=1
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP                                     A=0, M=X-1, D=1|0
  # A=M-1     // set the working address to the stack pointer                    A=X-1, M=MX, D=1|0
  # M=D     // set the value at the working address to the working value         A=X-1, M=1|0, D=1|0

  # and - pop the top two values from the stack, if the first is nonzero and the second is nonzero, push 1, otherwise push 0
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=D&M   // sub the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # @AND     // set working address to EQ                                         A=EQ, M=MEQ, D=MY-MX
  # D;JGT   // if the result is zero, jump to EQ                                 A=EQ, M=MEQ, D=MY-MX
  # D=0     // set the working value to zero                                     A=EQ, M=MEQ, D=0
  # @PUSH   // set the working address to PUSH                                   A=PUSH, M=MPUSH, D=0
  # D;JMP   // jump to PUSH irregardless
  # (AND)    // where EQ is
  # D=1     // set the working value to one                                      A=EQ, M=MEQ, D=1
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP                                     A=0, M=X-1, D=1|0
  # A=M-1     // set the working address to the stack pointer                    A=X-1, M=MX, D=1|0
  # M=D     // set the value at the working address to the working value         A=X-1, M=1|0, D=1|0

  # or - pop the top two values from the stack, if the first is nonzero or the second is nonzero, push 1, otherwise push 0
  # @SP     // get the stack pointer address                                     A=0, M=X, D=?
  # M=M-1   // decrement the stack pointer                                       A=0, M=X-1, D=?
  # A=M     // set the working address to our first value on the stack           A=X-1, M=MX, D=?
  # D=M     // set the working value to the top value of the stack               A=X-1, M=MX, D=MX
  # A=A-1   // decrement the working address to our second value on the stack    A=X-2, M=MX, D=MX
  # D=D|M   // sub the second value to the working value                         A=X-2, M=MY, D=MY-MX
  # @OR     // set working address to EQ                                         A=EQ, M=MEQ, D=MY-MX
  # D;JGT   // if the result is zero, jump to EQ                                 A=EQ, M=MEQ, D=MY-MX
  # D=0     // set the working value to zero                                     A=EQ, M=MEQ, D=0
  # @PUSH   // set the working address to PUSH                                   A=PUSH, M=MPUSH, D=0
  # D;JMP   // jump to PUSH irregardless
  # (OR)    // where EQ is
  # D=1     // set the working value to one                                      A=EQ, M=MEQ, D=1
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP                                     A=0, M=X-1, D=1|0
  # A=M-1   // set the working address to the stack pointer                    A=X-1, M=MX, D=1|0
  # M=D     // set the value at the working address to the working value         A=X-1, M=1|0, D=1|0

  # not - pop the top value from the stack, if it is nonzero, push 0, otherwise push 1
  # @SP     // get the stack pointer address
  # A=M-1   // set the working address to the top value of the stack
  # D=M     // set the working value to the top value of the stack
  # @ZERO   // set working address to ZERO
  # D;JEQ   // if the result is zero, jump to ZERO
  # D=0     // set the working value to zero
  # @PUSH   // set the working address to PUSH
  # D;JMP   // jump to PUSH irregardless
  # (ZERO)  // where ZERO is
  # D=1     // set the working value to one
  # (PUSH)  // where PUSH is
  # @SP     // set the working address to SP
  # A=M-1   // set the working address to the top value of the stack
  # M=D     // set the value at the working address to the working value

  def writeArithmetic(self, command: str):
    global COUNTER
    write = ""
    match command:
      case "add":
        write = "@SP\nM=M-1\nA=M\nD=M\nA=A-1\nD=D+M\nM=D\n"

      case "sub":
        write = """@SP
M=M-1
A=M  
D=M  
A=A-1
D=M-D       
M=D\n"""
      case "neg":
        write = """@SP  
D=M-1
A=D  
M=-M\n"""
      case "eq":
        write = f"""@SP  
M=M-1
A=M  
D=M  
A=A-1
D=M-D
@EQ{COUNTER}  
D;JEQ
D=0 
@PUSH{COUNTER}
D;JMP
(EQ{COUNTER}) 
D=-1  
(PUSH{COUNTER})
@SP  
A=M-1
M=D\n"""
      case "gt":
        write = f"""@SP
M=M-1 
A=M   
D=M   
A=A-1 
D=M-D 
@GT{COUNTER}   
D;JGT 
D=0   
@PUSH{COUNTER} 
D;JMP 
(GT{COUNTER})  
D=-1   
(PUSH{COUNTER})
@SP   
A=M-1 
M=D\n"""
      case "lt":
        write = f"""@SP  
M=M-1 
A=M   
D=M   
A=A-1 
D=M-D 
@LT{COUNTER}   
D;JLT 
D=0   
@PUSH{COUNTER} 
D;JMP 
(LT{COUNTER})  
D=-1   
(PUSH{COUNTER})
@SP   
A=M-1 
M=D\n"""
      case "and":
        write = f"""@SP   
M=M-1 
A=M   
D=M   
A=A-1 
D=D&M 
@AND{COUNTER}  
D;JGT 
D=0   
@PUSH{COUNTER} 
D;JMP 
(AND{COUNTER})   
(PUSH{COUNTER})
@SP   
A=M-1 
M=D\n"""
      case "or":
        write = f"""@SP   
M=M-1 
A=M   
D=M   
A=A-1 
D=D|M 
@OR{COUNTER}   
D;JGT 
D=0   
@PUSH{COUNTER} 
D;JMP 
(OR{COUNTER})  
(PUSH{COUNTER})
@SP   
A=M-1 
M=D\n"""
      case "not":
        write = f"""@SP   
A=M-1 
M=!M\n"""
    COUNTER += 1
    self.outputFile.write(write)

  # Writes to the output file the assembly code that implements the given push or pop command
  # psuedo-code:
  # RAM[SP]=i
  # SP++
  
  # //push segment i
  # @i
  # D=A       stores i in D
  # @SP
  # A=M
  # M=D       sets RAM[SP] to i
  # @SP
  # M=M+1     increments SP

  # psuedo-code:
  # addr <- segment + i
  # SP--
  # RAM[addr] <- RAM[SP]

  # //pop segment i
  # @segment
  # D=M
  # @i
  # D=D+A
  # @13
  # M=D       sets addr to the correct address of the segment
  # @SP
  # M=M-1     decrements SP
  # A=M
  # D=M
  # @13
  # M=D       sets RAM[addr] to the value popped from the stack

  def writePushPop(self, command: str, segment: str, index: int):
    if command == "C_PUSH":
      if segment == "constant":
        write = f"""@{index}
D=A
@SP
A=M
M=D
@SP
M=M+1\n"""
        self.outputFile.write(write)
        return
      seg = SEGMENTS[segment]
      if seg.isdigit():
        write = f"""@{seg}\nD=A\n
@{index}
D=D+A
A=D
D=M
@SP
A=M
M=D
@SP
M=M+1\n"""
      else:  
        write = f"""@{SEGMENTS[segment]}
D=M
@{index}
D=D+A
A=D
D=M
@SP
A=M
M=D
@SP
M=M+1\n"""
      self.outputFile.write(write)
      return
    seg = SEGMENTS[segment]
    if seg.isdigit():
      write = f"@{seg}\nD=A\n@{index}\nD=D+A\n@13\nM=D\n@SP\nM=M-1\nA=M\nD=M\n@13\nA=M\nM=D\n"
    else:
      write = f"@{SEGMENTS[segment]}\nD=M\n@{index}\nD=D+A\n@13\nM=D\n@SP\nM=M-1\nA=M\nD=M\n@13\nA=M\nM=D\n"
    self.outputFile.write(write)

  # Halts the VM
  def halt(self):
    self.outputFile.write("(HALT)\n@HALT\nD;JMP\n")

  # Closes the output file/stream
  def close(self):
    self.outputFile.close()

if __name__ == "__main__":
  vmTranslator = VMTranslator()
  vmTranslator.translate()