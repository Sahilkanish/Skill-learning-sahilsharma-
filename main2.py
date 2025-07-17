# create a function greet (name) that prints "hello,[name]!" //

def greet(name):
    print(f"hello,{name}!")
greet("sahil sharma")


# create a function add(a,b) that returns the sum of the two tumbers.call the function with inputs.//

def add(a,b):
    return a+b
result=add(10,25)
print(result)

#create a function display(*args)that accepts multiple arguments and print them.//

def display(*args):
    for arg in args:
        print(arg)
display("mango","apple","banana")


#create a fun. student_info(**kwargs)that accepts name,age,rollno as keywords arguments and print them.//

def student_info(**kwargs):
    for key, value in kwargs.items():
        print(f"{key.capitalize()}: {value}")
student_info(name="ram",age=20,rollno=123)
